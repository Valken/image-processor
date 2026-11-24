"""Assertions for the stateful infra stack.

The service stack isn't tested here: constructing it builds the Lambda bundling
Docker image, so its tests would need Docker running.
"""

import pytest
from aws_cdk import App
from aws_cdk.assertions import Match, Template
from image_processor_infra_stack import ImageProcessorInfraStack

# CloudFormation replaces a resource whenever its logical ID changes, and for
# these that means losing data, in-flight messages, or the CDN domain. If one
# of these fails, a construct ID or the construct tree changed: rename it back
# rather than updating the expected ID, unless the replacement is intended.
STATEFUL_LOGICAL_IDS = {
    "AWS::S3::Bucket": {"ImageBucket97210811"},
    "AWS::SQS::Queue": {
        "ImageProcessingQueue93F2F958",
        "ImageProcessingDeadLetterQueueDDCADF8E",
    },
    "AWS::CloudFront::Distribution": {"ImageDistribution0E4DF19E"},
}


def synth(environment: str) -> Template:
    stack = ImageProcessorInfraStack(
        App(), "ImageProcessorInfra", environment=environment
    )
    return Template.from_stack(stack)


@pytest.fixture(scope="module")
def dev() -> Template:
    return synth("dev")


@pytest.fixture(scope="module")
def prod() -> Template:
    return synth("prod")


@pytest.mark.parametrize("environment", ["dev", "prod"])
@pytest.mark.parametrize("resource_type", sorted(STATEFUL_LOGICAL_IDS))
def test_stateful_logical_ids_are_stable(environment: str, resource_type: str) -> None:
    resources = synth(environment).find_resources(resource_type)
    assert set(resources) == STATEFUL_LOGICAL_IDS[resource_type]


def test_prod_retains_stateful_resources(prod: Template) -> None:
    for resource_type in ("AWS::S3::Bucket", "AWS::SQS::Queue"):
        for resource in prod.find_resources(resource_type).values():
            assert resource["DeletionPolicy"] == "Retain"
            assert resource["UpdateReplacePolicy"] == "Retain"


def test_dev_deletes_stateful_resources(dev: Template) -> None:
    for resource_type in ("AWS::S3::Bucket", "AWS::SQS::Queue"):
        for resource in dev.find_resources(resource_type).values():
            assert resource["DeletionPolicy"] == "Delete"


def test_upload_queue_redrives_to_dead_letter_queue(dev: Template) -> None:
    dev.has_resource_properties(
        "AWS::SQS::Queue",
        {
            "RedrivePolicy": {
                "deadLetterTargetArn": {
                    "Fn::GetAtt": ["ImageProcessingDeadLetterQueueDDCADF8E", "Arn"]
                },
                "maxReceiveCount": 3,
            }
        },
    )


def test_upload_events_route_to_queue(dev: Template) -> None:
    dev.has_resource_properties(
        "AWS::Events::Rule",
        {
            "EventPattern": {
                "source": ["aws.s3"],
                "detail-type": ["Object Created"],
                "detail": Match.object_like(
                    {"object": {"key": [{"prefix": "uploads/"}]}}
                ),
            },
            "Targets": [
                Match.object_like(
                    {"Arn": {"Fn::GetAtt": ["ImageProcessingQueue93F2F958", "Arn"]}}
                )
            ],
        },
    )
