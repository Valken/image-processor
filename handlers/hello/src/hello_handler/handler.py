def handler(event: dict[str, object], context: object) -> dict[str, object]:
    return {
        "statusCode": 200,
        "body": "Hello from image-processor",
    }
