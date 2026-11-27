from typing import Any

from aws_cdk import Duration, Stack
from aws_cdk.aws_lambda_event_sources import SqsEventSource
from aws_cdk.aws_s3 import IBucket
from aws_cdk.aws_sqs import IQueue
from constructs import Construct

from uv_python_function import UvPythonFunction


class ImageProcessorServiceStack(Stack):
    """Stateless compute: Lambdas, API, and their IAM grants.

    Safe to redeploy (or destroy, in dev) at any time. Stateful resources come
    from ``ImageProcessorInfraStack`` and are passed in. References must only
    flow this way: grant on the Lambda's own role (``bucket.grant_*(fn)``,
    ``fn.add_event_source(...)``), never edit a stateful resource's policy to
    name something in this stack, or the two stacks become a dependency cycle.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        environment: str,
        image_bucket: IBucket,
        upload_queue: IQueue,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        UvPythonFunction(
            self,
            "HelloFunction",
            path="handlers/hello",
            handler="hello_handler.handler.handler",
            service_name="hello",
        )

        processor_function = UvPythonFunction(
            self,
            "ProcessorFunction",
            path="handlers/processor",
            handler="processor_handler.handler.handler",
            service_name="processor",
            memory_size=1769,  # one full vCPU
            timeout=Duration.seconds(45),  # under the 50 s ceiling, with headroom
        )
        processor_function.add_event_source(
            SqsEventSource(upload_queue, report_batch_item_failures=True)
        )
        image_bucket.grant_read(processor_function, "uploads/*")
        image_bucket.grant_write(processor_function, "processed/*")
