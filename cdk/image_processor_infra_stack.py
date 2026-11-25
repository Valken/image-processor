from typing import Any

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sqs as sqs
from constructs import Construct


class ImageProcessorInfraStack(Stack):
    """Stateful resources: storage, queues, tables, and the CDN in front of them.

    Changes rarely. Replacing anything here loses data or in-flight messages,
    and CloudFormation replaces a resource whenever its logical ID changes, so
    don't rename construct IDs here. The logical IDs are pinned in
    ``tests/cdk/test_infra_stack.py``. Never reference resources from the
    stateless service stack.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        environment: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        is_development = environment == "dev"
        bucket = s3.Bucket(
            self,
            "ImageBucket",
            auto_delete_objects=is_development,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            event_bridge_enabled=True,
            removal_policy=(
                RemovalPolicy.DESTROY if is_development else RemovalPolicy.RETAIN
            ),
        )
        self.image_bucket = bucket

        CfnOutput(self, "ImageBucketName", value=bucket.bucket_name)
        CfnOutput(self, "ImageBucketArn", value=bucket.bucket_arn)

        # Uploads flow S3 -> EventBridge -> SQS. Going via EventBridge (rather
        # than S3 bucket notifications to a Lambda) keeps every reference
        # inside this stack, so the stateless service stack can consume the
        # queue without creating a cross-stack dependency cycle.
        queue_removal_policy = (
            RemovalPolicy.DESTROY if is_development else RemovalPolicy.RETAIN
        )
        dead_letter_queue = sqs.Queue(
            self,
            "ImageProcessingDeadLetterQueue",
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            enforce_ssl=True,
            # Maximum retention, so failed uploads can be investigated/redriven.
            retention_period=Duration.days(14),
            removal_policy=queue_removal_policy,
        )
        upload_queue = sqs.Queue(
            self,
            "ImageProcessingQueue",
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            enforce_ssl=True,
            # Must be at least 6x the processor Lambda's timeout (AWS guidance
            # for SQS event sources). Revisit when the processor is added.
            visibility_timeout=Duration.seconds(300),
            dead_letter_queue=sqs.DeadLetterQueue(
                queue=dead_letter_queue,
                max_receive_count=3,
            ),
            removal_policy=queue_removal_policy,
        )
        self.upload_queue = upload_queue

        events.Rule(
            self,
            "ImageUploadEventRule",
            description="Trigger image processing on new uploads",
            event_pattern=events.EventPattern(
                source=["aws.s3"],
                detail_type=["Object Created"],
                detail={
                    "bucket": {"name": [bucket.bucket_name]},
                    "object": {"key": [{"prefix": "uploads/"}]},
                    "reason": ["PutObject"],
                },
            ),
            targets=[targets.SqsQueue(upload_queue)],
        )

        CfnOutput(self, "ImageProcessingQueueUrl", value=upload_queue.queue_url)
        CfnOutput(
            self,
            "ImageProcessingDeadLetterQueueUrl",
            value=dead_letter_queue.queue_url,
        )

        distribution = cloudfront.Distribution(
            self,
            "ImageDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(
                    bucket,
                    origin_path="/processed",
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            ),
        )

        # The OAC helper above grants this distribution's principal s3:GetObject
        # on the whole bucket (CDK does not scope it to origin_path). Add an
        # explicit deny, scoped to the same principal/distribution, for anything
        # outside processed/ so CloudFront can never serve raw uploads/.
        bucket.add_to_resource_policy(
            iam.PolicyStatement(
                effect=iam.Effect.DENY,
                actions=["s3:GetObject"],
                not_resources=[bucket.arn_for_objects("processed/*")],
                principals=[iam.ServicePrincipal("cloudfront.amazonaws.com")],
                conditions={
                    "StringEquals": {"AWS:SourceArn": distribution.distribution_arn}
                },
            )
        )
