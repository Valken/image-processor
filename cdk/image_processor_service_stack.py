from typing import Any

from aws_cdk import Duration, Stack
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk.aws_s3 import Bucket
from aws_cdk.aws_sqs import Queue as SqsQueue
from constructs import Construct


class ImageProcessorServiceStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        environment: str,
        image_bucket: Bucket,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # is_development = environment == "dev"
        queue = SqsQueue(
            self,
            "ImageProcessingQueue",
            visibility_timeout=Duration.seconds(300),
        )

        events.Rule(
            self,
            "ImageUploadEventRule",
            description="Trigger image processing on new uploads",
            event_pattern=events.EventPattern(
                source=["aws.s3"],
                detail_type=["Object Created"],
                detail={
                    "bucket": {"name": [image_bucket.bucket_name]},
                    "object": {"key": [{"prefix": "uploads/"}]},
                },
            ),
            targets=[targets.SqsQueue(queue)],
        )
