# Sizing the processor Lambda

How to measure the processor's duration and memory use, and choose its
`timeout` and `memory_size` from the results.

## Constraints

- **Timeout ceiling: 50 s.** The upload queue's visibility timeout (300 s,
  in the infra stack) must be at least 6× the function's timeout. Going
  higher means raising the visibility timeout too.
- **The timeout covers a whole batch.** The SQS event source uses the default
  batch size of 10, and images in a batch are processed one after another. If
  an invocation times out, the whole batch is reported as failed and every
  message in it is redelivered, including the ones that finished.
- **CPU scales with memory.** 1,769 MB is one full vCPU, and 512 MB (the
  `UvPythonFunction` default) is under a third of one. Pillow mostly uses one
  core, so memory beyond about 1,769 MB buys little extra speed.

## What Lambda reports

Every invocation ends with a report. The functions log in JSON
(`LoggingFormat.JSON`), so it arrives as a `platform.report` record:

```json
{
  "type": "platform.report",
  "record": {
    "requestId": "...",
    "metrics": {
      "durationMs": 8123.4,
      "billedDurationMs": 8124,
      "memorySizeMB": 1769,
      "maxMemoryUsedMB": 412,
      "initDurationMs": 702.1
    },
    "status": "success"
  }
}
```

- `durationMs`: the time for the whole batch, the number the timeout applies to.
- `maxMemoryUsedMB`: peak memory of the execution environment. Python rarely
  returns memory to the OS, so on a warm environment this is the high-water
  mark across invocations, not just this one.
- `initDurationMs`: only present on cold starts (importing Pillow and
  Powertools). It doesn't count towards the timeout.

The report alone doesn't say how many images a batch had or which one was
slow, so the handler should log, per image: the object key, size in bytes,
format, pixel dimensions and processing time. Log the batch size
(`len(event["Records"])`) once per invocation.

## Test inputs

Measure against the worst cases the processor accepts, not typical photos:

| Input | Why |
|---|---|
| A JPEG just under the upload limit | largest download and decode |
| An image at the pixel limit (the decompression-bomb check) | largest decoded size in memory |
| A large RGBA PNG | PNG decodes slowly, and the alpha channel adds a quarter more memory |
| A large HEIC photo from a phone | HEIC decodes more slowly than JPEG |
| A JPEG with an EXIF rotation | rotation costs an extra pass over the pixels |
| 10 worst-case images at once | a full batch, to measure against the timeout |

## Running a measurement

1. Deploy to dev.
2. Upload the test images with `put-object`, not `aws s3 cp`:

   ```bash
   aws s3api put-object --bucket <dev-bucket> --key uploads/<guid> \
     --body big.jpg --content-type image/jpeg
   ```

   `aws s3 cp` switches to multipart upload above 8 MB, which produces a
   `CompleteMultipartUpload` event. The EventBridge rule only matches
   `PutObject`, like a presigned PUT, so those uploads would never reach the
   processor.
3. For a full batch, upload 10 images in quick succession. Lambda doesn't wait
   to fill a batch, so check the logged batch size: a run that happened to
   arrive as several small batches doesn't measure the worst case.
4. Query the results in CloudWatch Logs Insights, on the processor's log group:

   ```
   filter type = "platform.report"
   | fields record.metrics.durationMs as duration,
            record.metrics.maxMemoryUsedMB as maxMemory,
            record.metrics.memorySizeMB as memory
   | stats count(*) as invocations, max(duration), pct(duration, 99), max(maxMemory)
     by memory
   ```

   Check the field names against a real record on the first run. The query
   assumes the JSON shape above.
5. Repeat at a few memory sizes, for example 1,024, 1,769 and 3,008 MB.
   Compare both duration and cost (memory in GB × billed seconds). More memory
   often costs about the same overall, because each invocation finishes sooner.
   [AWS Lambda Power Tuning](https://github.com/alexcasalboni/aws-lambda-power-tuning)
   automates this sweep if it's needed more than once.

## Choosing the values

- **Memory:** about 1.5× the highest `maxMemoryUsedMB` seen, rounded up, and
  at least the size that gave acceptable speed.
- **Timeout:** about 2× the slowest full batch, and no more than 50 s.
- **If the slowest batch is close to 50 s:** lower the event source's
  `batch_size` rather than raising the timeout, so the infra stack's visibility
  timeout can stay as it is. Otherwise, raise both together.

If the numbers come out too high, see whether JPEGs can be decoded at reduced
scale with `img.draft("RGB", (width, height))` before loading. Both outputs are
much smaller than a typical upload, so this cuts decode time and memory
sharply.

## Measuring locally

Local timings are only useful for comparing changes to the processing code
(for example, before and after adding `draft`). A Mac is faster than a Lambda
vCPU, so don't use them to set the timeout. For memory, read the peak resident
size with `resource.getrusage(resource.RUSAGE_SELF).ru_maxrss` (bytes on macOS,
kilobytes on Linux). `tracemalloc` doesn't see Pillow's pixel buffers, which
are allocated in C.

## Keeping an eye on it

Once the values are set, alarm when the p99 duration goes above about 80% of
the timeout. Larger uploads or a code change can creep towards the limit, and
a timeout fails the whole batch.
