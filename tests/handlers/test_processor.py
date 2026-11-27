from dataclasses import dataclass

from processor_handler.handler import handler


@dataclass
class FakeLambdaContext:
    function_name: str = "test"
    invoked_function_arn: str = "arn:aws:lambda:us-east-1:123456789012:function:test"
    memory_limit_in_mb: int = 128
    aws_request_id: str = "12345678-1234-5678-1234-567812345678"


def test_only_malformed_message_is_reported_as_failure():
    event = {
        "Records": [
            {"messageId": "m1", "body": '{"detail": {}}'},
            {"messageId": "m2", "body": "nope"},
        ]
    }
    result = handler(event, FakeLambdaContext())
    assert result == {"batchItemFailures": [{"itemIdentifier": "m2"}]}


def test_all_messages_are_successful():
    event = {
        "Records": [
            {"messageId": "m1", "body": '{"detail": {}}'},
            {"messageId": "m2", "body": '{"detail": {}}'},
        ]
    }
    result = handler(event, FakeLambdaContext())
    assert result == {"batchItemFailures": []}
