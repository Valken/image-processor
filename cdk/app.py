from aws_cdk import App
from image_processor_infra_stack import ImageProcessorInfraStack
from image_processor_service_stack import ImageProcessorServiceStack

VALID_ENVIRONMENTS = {"dev", "prod"}


app = App()
environment = app.node.try_get_context("environment")

if environment not in VALID_ENVIRONMENTS:
    allowed_environments = ", ".join(sorted(VALID_ENVIRONMENTS))
    raise ValueError(
        "The 'environment' context must be one of "
        f"{allowed_environments}; for example: --context environment=dev"
    )

stack_name = f"image-processor-infra-{environment}"
infra_stack = ImageProcessorInfraStack(
    app,
    "ImageProcessorInfra",
    environment=environment,
    stack_name=stack_name,
)

service_stack = ImageProcessorServiceStack(
    app,
    "ImageProcessorService",
    environment=environment,
    image_bucket=infra_stack.image_bucket,
    stack_name=f"image-processor-service-{environment}",
)
service_stack.add_dependency(infra_stack)


app.synth()
