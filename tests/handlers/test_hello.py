from hello_handler.handler import handler


def test_handler_returns_hello_response() -> None:
    assert handler({}, object()) == {
        "statusCode": 200,
        "body": "Hello from image-processor",
    }
