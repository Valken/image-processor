"""Lambda function bundled from a uv workspace member.

Each handler lives in its own workspace member under ``handlers/<name>/``: a
``pyproject.toml`` with the package directly beside it (flat layout, no
``src/``). This construct installs that member and its locked runtime
dependency closure (from the root ``uv.lock``) directly into the Lambda asset,
so multi-module handlers and workspace libraries work without copying files by
hand.
"""

import tomllib
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Any

from aws_cdk import BundlingOptions, DockerImage, Duration, IgnoreMode, aws_logs
from aws_cdk import aws_lambda as lambda_
from constructs import Construct

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BUNDLING_IMAGE_DIR = Path(__file__).resolve().parent / "bundling"
DEFAULT_TIMEOUT = Duration.seconds(30)


@cache
def _bundling_image() -> DockerImage:
    # Build from a dedicated context dir: CDK tags the image with a fingerprint
    # of the whole context (ignoring .dockerignore), and that tag feeds the
    # Lambda asset hash. Using the repo root would pull in cdk.out/IDE files and
    # produce a new hash on every synth.
    return DockerImage.from_build(str(BUNDLING_IMAGE_DIR), platform="linux/amd64")


def _package_name(member_dir: Path) -> str:
    with (member_dir / "pyproject.toml").open("rb") as f:
        return tomllib.load(f)["project"]["name"]


def _asset_excludes(member_path: str) -> list[str]:
    # Allowlist only what the bundle needs. The asset hash is a fingerprint of
    # these source files, so anything else in the repo (other handlers, CDK
    # code, IDE files, cdk.out) must not leak in, or unrelated changes would
    # redeploy this function. Every member's pyproject.toml is included because
    # uv needs the full workspace layout to read the lockfile.
    #
    # Bundling mounts the whole project root, not just these files, so a
    # workspace library the handler depends on gets installed even when it's
    # missing here. It must still be listed, or edits to it won't change the
    # hash and the cached asset is redeployed unchanged. All of libs/ is
    # included, so a library change redeploys every handler, including ones
    # that don't use it.
    return [
        "*",
        "!pyproject.toml",
        "!uv.lock",
        "!handlers/*/pyproject.toml",
        "!libs",
        f"!{member_path}",
        "**/__pycache__",
        "**/.ruff_cache",
        "**/.pytest_cache",
    ]


def _bundling_command(package: str) -> list[str]:
    # Install the member itself (non-editable) plus its locked runtime deps
    # straight into the output, with no venv, so the bundle contains only what
    # Lambda needs.
    script = "\n".join(
        [
            "cd /asset-input",
            (
                f"uv export --frozen --no-dev --package {package} "
                "--no-editable --no-hashes "
                "| uv pip install --no-deps --python python3.14 "
                "--target /asset-output -r -"
            ),
        ]
    )
    return ["bash", "-ec", script]


class UvPythonFunction(lambda_.Function):
    """A Python Lambda built from a uv workspace member.

    :param path: the member's directory relative to the project root,
        e.g. ``"handlers/hello"``. The package name is read from its
        ``pyproject.toml``.
    :param handler: the Lambda handler, e.g. ``"hello_handler.handler.handler"``.
    :param service_name: value for ``POWERTOOLS_SERVICE_NAME``, which tags
        Powertools logs, metrics and traces.
    :param timeout: function timeout. Defaults to 30 seconds.
    :param memory_size: memory in MB (CPU scales with it). Defaults to 512.
    :param log_retention: retention for the function's log group. Defaults to
        one month.
    :param tracing: X-Ray tracing mode. Defaults to active.
    :param environment: extra environment variables, merged over
        ``POWERTOOLS_SERVICE_NAME``.
    :param kwargs: any other ``lambda_.Function`` props (``layers``,
        ``reserved_concurrent_executions``, ``vpc``, ...). ``code``,
        ``runtime``, ``architecture``, ``log_group`` and ``logging_format``
        are set by this construct.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        path: str,
        handler: str,
        service_name: str,
        timeout: Duration = DEFAULT_TIMEOUT,
        memory_size: int = 512,
        log_retention: aws_logs.RetentionDays = aws_logs.RetentionDays.ONE_MONTH,
        tracing: lambda_.Tracing = lambda_.Tracing.ACTIVE,
        environment: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> None:
        member_path = path.strip("/")
        package = _package_name(PROJECT_ROOT / member_path)

        log_group = aws_logs.LogGroup(
            scope, f"{construct_id}LogGroup", retention=log_retention
        )

        super().__init__(
            scope,
            construct_id,
            runtime=lambda_.Runtime.PYTHON_3_14,
            architecture=lambda_.Architecture.X86_64,
            handler=handler,
            timeout=timeout,
            memory_size=memory_size,
            log_group=log_group,
            logging_format=lambda_.LoggingFormat.JSON,
            tracing=tracing,
            environment={
                "POWERTOOLS_SERVICE_NAME": service_name,
                **(environment or {}),
            },
            code=lambda_.Code.from_asset(
                str(PROJECT_ROOT),
                exclude=_asset_excludes(member_path),
                ignore_mode=IgnoreMode.DOCKER,
                bundling=BundlingOptions(
                    image=_bundling_image(),
                    command=_bundling_command(package),
                ),
            ),
            **kwargs,
        )
