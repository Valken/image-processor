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
    `attribute_exists(image_id) AND status_rank <= :rank`.
    - `<=` so a repeated transition (e.g. retried `processing`) is a no-op.
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
| `ImageRecordStore` | Moto DynamoDB, in `tests/common/` | Each transition; backwards → `False` and unchanged; repeat; missing record; `create` collision |

## Doc updates to make

- **Code Layout**: `libs/common` row → "the `ImageRecord` model, the `Status`
  enum and its ordering, and `ImageRecordStore`"; dependencies "Pydantic,
  boto3". Paragraph under the table: both Lambdas use `ImageRecordStore`;
  which Lambda may do what is enforced by IAM.
- **New "Processor modules"** subsection with the table above.
- **New "Upload Record"** section: the store's methods, conditions, ranking,
  no-op on backwards moves, failure reason, missing record, ownership check,
  IAM.
- **Persistence & State Transitions**: replace the "conditional writes,
  implemented once in `common`" bullet with a link to Upload Record.
- **API Definition**: add `reason` to the `GET /status` response (present only
  when `failed`; `images` only when `complete`).
- **Naming**: the `GET /status` response says `full`, the S3 keys say
  `display.webp`. Pick one (probably `display`).
