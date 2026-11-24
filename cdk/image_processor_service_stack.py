from typing import Any

from aws_cdk import CfnOutput, Stack
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

        hello_function = UvPythonFunction(
            self,
            "HelloFunction",
            path="handlers/hello",
            handler="hello_handler.handler.handler",
            service_name="hello",
        )
        CfnOutput(self, "HelloFunctionArn", value=hello_function.function_arn)
