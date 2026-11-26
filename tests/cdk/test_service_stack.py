"""Assertions for the stateless service stack.

Synthesizing this stack bundles every Lambda, so these tests need Docker.
"""

import pytest
from aws_cdk import App
from aws_cdk.assertions import Match, Template
from image_processor_infra_stack import ImageProcessorInfraStack
from image_processor_service_stack import ImageProcessorServiceStack


@pytest.fixture(scope="module")
def template() -> Template:
    app = App()
    infra = ImageProcessorInfraStack(app, "ImageProcessorInfra", environment="dev")
    service = ImageProcessorServiceStack(
        app,
        "ImageProcessorService",
        environment="dev",
        image_bucket=infra.image_bucket,
        upload_queue=infra.upload_queue,
    )
    return Template.from_stack(service)


def test_hello_function_uses_uv_python_function_defaults(template: Template) -> None:
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "Handler": "hello_handler.handler.handler",
            "Runtime": "python3.14",
            "Architectures": ["x86_64"],
            "MemorySize": 512,
            "Timeout": 30,
            "TracingConfig": {"Mode": "Active"},
            "LoggingConfig": Match.object_like({"LogFormat": "JSON"}),
            "Environment": {"Variables": {"POWERTOOLS_SERVICE_NAME": "hello"}},
        },
    )


def test_function_logs_to_its_own_log_group_with_retention(
    template: Template,
) -> None:
    (function,) = template.find_resources("AWS::Lambda::Function").values()
    log_group_id = function["Properties"]["LoggingConfig"]["LogGroup"]["Ref"]
    log_group = template.find_resources("AWS::Logs::LogGroup")[log_group_id]
    assert log_group["Properties"]["RetentionInDays"] == 30
