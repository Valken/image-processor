import json
from dataclasses import dataclass

from aws_lambda_powertools.utilities.parser.models import (
    S3EventNotificationEventBridgeModel,
)

from processor_handler.handler import handler


@dataclass
class FakeLambdaContext:
    function_name: str = "test"
    invoked_function_arn: str = "arn:aws:lambda:us-east-1:123456789012:function:test"
    memory_limit_in_mb: int = 128
    aws_request_id: str = "12345678-1234-5678-1234-567812345678"


records = {
    "Records": [
        {
            "messageId": "1df0af09-d21b-44ab-9ff8-654b1fd536e6",
            "receiptHandle": "AQEBzX1e0Sibd8JIquB2o9Uuca90/9BAB58U0uVw4UB2NMezMMn4/fpSilXC4BERG9fOsd8F3FKyC6Bje4wcQ5OKbG2vSRMQX344hMM/S9wtyboJvbJoM24OOaTMNHuk5AhZkYobNQn9calQTECIpma+TRMXsndZNXMD79Bm4mwLiwzeq55/3YBoWg9XYY6c8Ep2xBKPfpBiypWE0aamPPUYFu/IInatFmgQa8SuQ9vYs3wrU0YStX0TPRTpzdfWudXrnVGUGT7n6y2QqtiyHwJEoAJLagVcl9PR7A0oVG4F0I2IjeZ6kJ1gsnqg/rMHoFX1qHbfzOvIITrbT9pCbjZvKRxNtDjdruL1DZHQIOMCPEptJppYGs3vj41Wwvu1YYUaMoXuEcj2Byj4zHff//NFXE9l4NV5WtMNmxHdEN/9tO3Ue7SWpAhoMak6lw8NefTNwz91xq3mcxiloUohEYJnGg==",
            "body": '{"version":"0","id":"35bb698b-b120-2e29-7620-b96aeaabcee0","detail-type":"Object Created","source":"aws.s3","account":"729800136817","time":"2026-11-28T12:55:45Z","region":"eu-west-1","resources":["arn:aws:s3:::image-processor-infra-dev-imagebucket97210811-9djx8oas0tcp"],"detail":{"version":"0","event-version":"1.2","bucket":{"name":"image-processor-infra-dev-imagebucket97210811-9djx8oas0tcp","aws-generated-tags":{"aws:cloudformation:stack-id":"arn:aws:cloudformation:eu-west-1:729800136817:stack/image-processor-infra-dev/c9a60da0-9829-11f1-8aad-0a95dc4c0a03","aws:cloudformation:logical-id":"ImageBucket97210811","aws:cloudformation:stack-name":"image-processor-infra-dev"}},"object":{"key":"uploads/12345","size":215904,"etag":"6503890a302b34a1ccc74df09814870d","sequencer":"006B0ACF516EE200C0"},"request-id":"FFTAFHM09K4YS487","requester":"729800136817","source-ip-address":"79.97.100.13","reason":"PutObject"}}',
            "attributes": {
                "ApproximateReceiveCount": "1",
                "SentTimestamp": "1795870546221",
                "SenderId": "AIDAJ2E4ZHTZPIG4AM4I6",
                "ApproximateFirstReceiveTimestamp": "1795870546228",
            },
            "messageAttributes": {},
            "md5OfBody": "2c335c92c2c05232a31bacf041b064ee",
            "eventSource": "aws:sqs",
            "eventSourceARN": "arn:aws:sqs:eu-west-1:729800136817:image-processor-infra-dev-ImageProcessingQueue93F2F958-Kq5lsnd1iH3q",
            "awsRegion": "eu-west-1",
        }
    ]
}

s3_something_else = {
    "version": "0",
    "id": "fa203bf2-cca0-9153-538f-3f7d4c3c63a0",
    "detail-type": "Object Created",
    "source": "aws.s3",
    "account": "729800136817",
    "time": "2026-11-27T21:47:47Z",
    "region": "eu-west-1",
    "resources": [
        "arn:aws:s3:::image-processor-infra-dev-imagebucket97210811-9djx8oas0tcp"
    ],
    "detail": {
        "version": "0",
        "event-version": "1.2",
        "bucket": {
            "name": "image-processor-infra-dev-imagebucket97210811-9djx8oas0tcp",
            # "aws-generated-tags": {
            #   "aws:cloudformation:stack-id": "arn:aws:cloudformation:eu-west-1:729800136817:stack/image-processor-infra-dev/c9a60da0-9829-11f1-8aad-0a95dc4c0a03",
            #   "aws:cloudformation:logical-id": "ImageBucket97210811",
            #   "aws:cloudformation:stack-name": "image-processor-infra-dev"
            # }
        },
        "object": {
            "key": "uploads/12345",
            "size": 215904,
            # "etag": "6503890a302b34a1ccc74df09814870d",
            # "sequencer": "006B09FA8328EBB62A"
        },
        "request-id": "5NM64EMVZB5X7P6T",
        "requester": "729800136817",
        # "source-ip-address": "79.97.100.13",
        "reason": "PutObject",
    },
}

other_records = {
    "Records": [
        {
            "messageId": "059f36b4-87a3-44ab-83d2-661975830a7d",
            "receiptHandle": "AQEBwJnKyrHigUMZj6rYigCgxlaS3SLy0a...",
            "body": json.dumps(s3_something_else),
            "attributes": {
                "ApproximateReceiveCount": "1",
                "SentTimestamp": "1545082649183",
                "SenderId": "AIDAIENQZJOLO23YVJ4VO",
                "ApproximateFirstReceiveTimestamp": "1545082649185",
            },
            "messageAttributes": {
                "myAttribute": {
                    "stringValue": "myValue",
                    "stringListValues": [],
                    "binaryListValues": [],
                    "dataType": "String",
                }
            },
            "md5OfBody": "e4e68fb7bd0e697a0ae8f1bb342846b3",
            "eventSource": "aws:sqs",
            "eventSourceARN": "arn:aws:sqs:us-east-2:123456789012:my-queue",
            "awsRegion": "us-east-2",
        },
        {
            "messageId": "2e1424d4-f796-459a-8184-9c92662be6da",
            "receiptHandle": "AQEBzWwaftRI0KuVm4tP+/7q1rGgNqicHq...",
            "body": json.dumps(s3_something_else),
            "attributes": {
                "ApproximateReceiveCount": "1",
                "SentTimestamp": "1545082650636",
                "SenderId": "AIDAIENQZJOLO23YVJ4VO",
                "ApproximateFirstReceiveTimestamp": "1545082650649",
            },
            "messageAttributes": {},
            "md5OfBody": "e4e68fb7bd0e697a0ae8f1bb342846b3",
            "eventSource": "aws:sqs",
            "eventSourceARN": "arn:aws:sqs:us-east-2:123456789012:my-queue",
            "awsRegion": "us-east-2",
        },
    ]
}

# Pydantic expects a lot more fields than just passing in route event shapes, so specify everything
# based off same events
# https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html#example-standard-queue-message-event
# https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html#example-standard-queue-message-event


def test_create_envelope_works():
    S3EventNotificationEventBridgeModel.model_validate(s3_something_else)


def test_only_malformed_message_is_reported_as_failure():
    event = {
        "Records": [
            {"messageId": "m1", "body": f"{s3_something_else}"},
            {"messageId": "m2", "body": "nope"},
        ]
    }
    result = handler(event, FakeLambdaContext())
    assert result == {"batchItemFailures": [{"itemIdentifier": "m2"}]}


def test_all_messages_are_successful():
    result = handler(other_records, FakeLambdaContext())
    assert result == {"batchItemFailures": []}
