from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.batch import (
    BatchProcessor,
    EventType,
    process_partial_response,
)
from aws_lambda_powertools.utilities.parser.models import (
    S3EventNotificationEventBridgeModel,
    SqsRecordModel,
)
from aws_lambda_powertools.utilities.parser.types import Json
from aws_lambda_powertools.utilities.typing import LambdaContext


class S3NotificationSqsRecord(SqsRecordModel):  # type: ignore[override]
    body: Json[
        S3EventNotificationEventBridgeModel
    ]  # deserialize S3 put event data from JSON string


processor = BatchProcessor(event_type=EventType.SQS, model=S3NotificationSqsRecord)
tracer = Tracer()
logger = Logger()


@tracer.capture_method
def record_handler(record: S3NotificationSqsRecord):
    logger.info(record.body.detail)


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def handler(event, context: LambdaContext):
    return process_partial_response(
        event=event,
        record_handler=record_handler,
        processor=processor,
        context=context,
    )
