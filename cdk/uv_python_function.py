"""Lambda function bundled from a uv workspace member.

Each handler lives in its own workspace member under ``handlers/<name>/`` with a
``pyproject.toml`` and a src-layout package. This construct installs that member
and its locked runtime dependency closure (from the root ``uv.lock``) directly
into the Lambda asset, so multi-module handlers and workspace libraries work
without copying files by hand.
"""

import tomllib
from functools import cache
from pathlib import Path
from typing import Any

from aws_cdk import BundlingOptions, DockerImage, IgnoreMode
from aws_cdk import aws_lambda as lambda_
from constructs import Construct

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BUNDLING_IMAGE_DIR = Path(__file__).resolve().parent / "bundling"


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
    return [
        "*",
        "!pyproject.toml",
        "!uv.lock",
        "!handlers/*/pyproject.toml",
        f"!{member_path}",
        f"{member_path}/tests",
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
    :param kwargs: any other ``lambda_.Function`` props (timeout, memory_size,
        environment, ...). ``code``, ``runtime`` and ``architecture`` are set by
        this construct.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        path: str,
        handler: str,
        **kwargs: Any,
    ) -> None:
        member_path = path.strip("/")
        package = _package_name(PROJECT_ROOT / member_path)

        super().__init__(
            scope,
            construct_id,
            runtime=lambda_.Runtime.PYTHON_3_14,
            architecture=lambda_.Architecture.X86_64,
            handler=handler,
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
