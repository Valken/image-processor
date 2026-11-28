# Processor & Upload Record — Working Notes

Decisions from design discussion, to build from. `docs/design.md` gets
updated once the code exists (see [Doc updates to make](#doc-updates-to-make)).

## `common`

- `models.py`: `ImageRecord` model (including `reason`) and `Status` enum with
  a rank (`pending` 0, `processing` 1, `complete` 2, `failed` 2).
- `store.py`: `ImageRecordStore`, wrapping the DynamoDB table (passed in).
  - `create(image_id, client_id)`: writes `pending` + `status_rank`,
    `client_id`, TTL, `created_at`. Condition: `attribute_not_exists(image_id)`.
  - `get(image_id) -> ImageRecord | None`: plain read, no ownership check.
  - `mark_processing(image_id)`, `mark_complete(image_id)`,
    `mark_failed(image_id, reason)`: thin wrappers over a private
    `_transition(image_id, status, **fields) -> bool`.
  - `_transition`: the only `update_item` call. Sets `status`, `status_rank`,
    `updated_at` and any extra fields. Condition:
    `attribute_exists(image_id) AND (status_rank < :rank OR #status = :status)`.
    - A repeated identical transition (e.g. retried `processing`) succeeds
      and changes nothing.
    - `complete` and `failed` share a rank but can't overwrite each other, so
      a finished state is final. (Plain `status_rank <= :rank` would let a
      duplicate delivery turn `complete` into `failed`.)
    - A failed condition check returns `False`; the caller logs it and skips.
    - Any other DynamoDB error propagates (transient).
- Named `mark_*` methods rather than `mark(status)`: `failed` takes a reason
  the others don't, and there's no `mark_pending` for the processor to misuse.
- `boto3` is a dependency of `common`.

## Processor

| Module | Responsibility |
|---|---|
| `handler.py` | Powertools `BatchProcessor`. Unpacks the EventBridge Object Created event inside each SQS body into bucket, key, size and guid (from `uploads/{guid}`). Checks byte size before any download. `PermanentError` → `mark_failed` and return success; anything else propagates → batch item failure. |
| `processor.py` | `get` record (for `client_id` logging; missing record is permanent), `mark_processing` (stop if `False`), read `uploads/{guid}`, produce each variant via `image`, write `processed/{guid}/thumb.webp` and `display.webp`, `mark_complete`. S3 client and store are passed in. Doesn't catch AWS errors. |
| `image.py` | Bytes in, WebP bytes out, no AWS code. Raises `PermanentError` for `UnidentifiedImageError`, decompression bombs and truncated files. |

- `PermanentError` lives in the processor package.
- Image handling to remember: RGBA/palette/CMYK modes (CMYK needs converting),
  EXIF orientation (`ImageOps.exif_transpose`), images under the min width are
  left unchanged.
- HEIC needs `pillow-heif` and `register_heif_opener()`.
- Pillow only warns at `MAX_IMAGE_PIXELS` and raises at 2×; treat the warning
  as an error or account for it.

## Failure modes

What idempotent writes already cover: duplicate deliveries, retries after a
partial failure (outputs overwrite the same keys), two runs of the same
message at once, and transient AWS errors (propagate → SQS retries).

Still to handle:

- **Retries run out and the image stays `processing`.** A transient error
  that persists for 3 receives sends the message to the DLQ with nothing
  setting `failed`, so the client polls `processing` forever. Lambda timeouts
  and out-of-memory errors on a particular image end up the same way.
  - A small DLQ consumer that calls
    `mark_failed(reason="processing gave up")`.
  - An alarm on DLQ depth.
  - Optionally, the API reports a record that has been `processing` too long
    as failed.
- **Re-uploads.** A presigned URL works more than once until it expires. A
  different image uploaded to the same URL after `complete` is skipped and the
  old output stays. Keep the expiry short; if it matters, store the object's
  ETag on the record and only skip a message whose ETag matches.
- **Sustained throttling** uses up the 3 receives quickly and ends in the
  stuck-`processing` case. Set boto3's retry mode to `adaptive` (or
  `standard`) and put a maximum concurrency on the event source mapping.

## API

- `POST /upload` → `store.create(image_id, client_id)`.
- `GET /status/{image_id}` → `store.get`; 404 if missing or
  `record.client_id != caller`. Returns `reason` when `failed`.

## IAM

- API role: `PutItem`, `GetItem`.
- Processor role: `GetItem`, `UpdateItem`.
- Assert these in the CDK stack tests.

## Tests

| Layer | Fixtures | Check |
|---|---|---|
| `image` | Generated images in `tests/handlers/processor/conftest.py` (parametrised formats/modes, small image, pixel bomb via monkeypatched `MAX_IMAGE_PIXELS`) | Output format, width, orientation; bad input → `PermanentError` |
| `processor` | Moto S3 (or in-memory fake) + fake store | Both outputs at the right keys; `processing` → `complete`; idempotent on rerun |
| `handler` | Sample EventBridge-in-SQS event, `processor` stubbed | Permanent → `failed` + deleted; transient → `batchItemFailures`; size limit |
| `ImageRecordStore` | Moto DynamoDB, in `tests/common/` | Each transition; backwards → `False` and unchanged; repeat; `complete` → `failed` and `failed` → `complete` → `False`; missing record; `create` collision |

### Moto for the store tests

- Add `moto[dynamodb]` to the root `dev` dependency group.
- Why moto over testcontainers + DynamoDB Local: in-process and fast, a fresh
  table per test, and it evaluates condition expressions (`attribute_exists`,
  `attribute_not_exists`, `OR`, `<`) and raises
  `ConditionalCheckFailedException` like the real service.
- DynamoDB Local is worth it only for edge-case semantics moto may not match
  (transactions, unusual update expressions, exact limits), or for one
  end-to-end integration test.
- Don't use botocore's `Stubber`: it returns scripted responses and never
  evaluates the condition, so it can't prove the condition is right.
- Keep the fixture's key schema the same as the CDK table definition.

```python
# tests/common/conftest.py
import boto3
import pytest
from moto import mock_aws

from common.store import ImageRecordStore


@pytest.fixture
def store():
    with mock_aws():
        table = boto3.resource("dynamodb", region_name="us-east-1").create_table(
            TableName="ImageRecords",
            KeySchema=[{"AttributeName": "image_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "image_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield ImageRecordStore(table)
```

## Naming and config

- Table: `ImageRecords` (CDK construct ID). Leave `table_name` unset so
  CloudFormation generates the physical name.
- Model: `ImageRecord`. Class: `ImageRecordStore`.
- Pass the table name to each Lambda as `IMAGE_RECORDS_TABLE`; build the
  `boto3` table and `ImageRecordStore` once at module level.

## Dependencies

- Each package lists what its own code imports. `common` lists `pydantic` and
  `boto3`; the processor lists `pydantic` too only if it imports it directly.
- One `uv.lock` means one version across the workspace, so listing a package
  in several members can't conflict.
- Test-only packages (`moto`, `pytest`) go in the root `dev` group.

## Doc updates to make

- **Code Layout**: `libs/common` row → "the `ImageRecord` model, the `Status`
  enum and its ordering, and `ImageRecordStore`"; dependencies "Pydantic,
  boto3". Paragraph under the table: both Lambdas use `ImageRecordStore`;
  which Lambda may do what is enforced by IAM.
- **New "Processor modules"** subsection with the table above.
- **New "Upload Record"** section: the store's methods, conditions, ranking,
  no-op on backwards moves, finished states are final, failure reason, missing
  record, ownership check, IAM.
- **Error Handling & Retry Strategy**: a DLQ'd message must end as `failed`
  (DLQ consumer + alarm), not stuck at `processing`.
- **Persistence & State Transitions**: replace the "conditional writes,
  implemented once in `common`" bullet with a link to Upload Record.
- **API Definition**: add `reason` to the `GET /status` response (present only
  when `failed`; `images` only when `complete`).
- **Naming**: the `GET /status` response says `full`, the S3 keys say
  `display.webp`. Pick one (probably `display`).
