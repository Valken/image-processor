from typing import Any

from aws_cdk import CfnOutput, RemovalPolicy, Stack
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
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

        CfnOutput(
            self,
            "ImageDistributionDomainName",
            value=distribution.distribution_domain_name,
        )
        CfnOutput(self, "ImageDistributionId", value=distribution.distribution_id)
