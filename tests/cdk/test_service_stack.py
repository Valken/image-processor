"""Assertions for the stateless service stack.

Synthesizing this stack bundles every Lambda, so these tests need Docker.
"""

import importlib

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


def test_each_function_logs_to_its_own_log_group_with_retention(
    template: Template,
) -> None:
    functions = template.find_resources("AWS::Lambda::Function")
    log_groups = template.find_resources("AWS::Logs::LogGroup")
    log_group_ids = [
        function["Properties"]["LoggingConfig"]["LogGroup"]["Ref"]
        for function in functions.values()
    ]
    assert len(set(log_group_ids)) == len(functions)
    for log_group_id in log_group_ids:
        assert log_groups[log_group_id]["Properties"]["RetentionInDays"] == 30


def test_each_function_handler_resolves_to_a_callable(template: Template) -> None:
    # A wrong handler string synthesizes and deploys fine, then fails every
    # invocation with Runtime.ImportModuleError. Every member is installed in
    # the venv (uv sync --all-packages), so import each handler from there.
    for function in template.find_resources("AWS::Lambda::Function").values():
        handler = function["Properties"]["Handler"]
        module_name, _, attribute = handler.rpartition(".")
        module = importlib.import_module(module_name)
        assert callable(getattr(module, attribute, None)), handler


def test_processor_consumes_upload_queue_with_partial_batch_failures(
    template: Template,
) -> None:
    template.has_resource_properties(
        "AWS::Lambda::EventSourceMapping",
        {
            "FunctionName": {"Ref": Match.string_like_regexp("^ProcessorFunction")},
            "FunctionResponseTypes": ["ReportBatchItemFailures"],
        },
    )
