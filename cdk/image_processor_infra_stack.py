from typing import Any

from aws_cdk import CfnOutput, RemovalPolicy, Stack, aws_s3 as s3
from constructs import Construct


class ImageProcessorInfraStack(Stack):
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
            removal_policy=(
                RemovalPolicy.DESTROY if is_development else RemovalPolicy.RETAIN
            ),
        )

        CfnOutput(self, "ImageBucketName", value=bucket.bucket_name)
        CfnOutput(self, "ImageBucketArn", value=bucket.bucket_arn)
