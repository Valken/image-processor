"""The Lambda asset hash must change exactly when the bundle's inputs change.

CDK bundles from the whole project root, but hashes only the files that
survive ``_asset_excludes``. If a file the bundle uses is missing from the
hash, edits to it are silently not deployed (the cached asset is reused).
These tests fingerprint a throwaway workspace the same way
``UvPythonFunction`` does, so no Docker or synth is needed.
"""

from pathlib import Path

import pytest
from aws_cdk import FileSystem, IgnoreMode

from uv_python_function import _asset_excludes

FILES = {
    "pyproject.toml": "[project]\nname = 'root'\n",
    "uv.lock": "version = 1\n",
    "handlers/api/pyproject.toml": "[project]\nname = 'api-handler'\n",
    "handlers/api/api_handler/handler.py": "def handler(e, c): ...\n",
    "handlers/other/pyproject.toml": "[project]\nname = 'other-handler'\n",
    "handlers/other/other_handler/handler.py": "def handler(e, c): ...\n",
    "libs/common/pyproject.toml": "[project]\nname = 'common'\n",
    "libs/common/common/__init__.py": "X = 1\n",
    "cdk/app.py": "app = 1\n",
    "tests/test_api.py": "def test(): ...\n",
    "README.md": "# readme\n",
}


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    for name, content in FILES.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return tmp_path


def fingerprint(root: Path, member: str = "handlers/api") -> str:
    return FileSystem.fingerprint(
        str(root), exclude=_asset_excludes(member), ignore_mode=IgnoreMode.DOCKER
    )


def edit(root: Path, name: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write("# edited\n")


@pytest.mark.parametrize(
    "changed",
    [
        "handlers/api/api_handler/handler.py",  # own source
        "handlers/api/api_handler/new_module.py",  # new file in own source
        "libs/common/common/__init__.py",  # workspace library it depends on
        "uv.lock",  # locked dependency versions
    ],
)
def test_bundle_inputs_change_the_hash(workspace: Path, changed: str) -> None:
    before = fingerprint(workspace)
    edit(workspace, changed)
    assert fingerprint(workspace) != before


@pytest.mark.parametrize(
    "changed",
    [
        "handlers/other/other_handler/handler.py",  # another handler's source
        "cdk/app.py",
        "tests/test_api.py",
        "README.md",
        "handlers/api/api_handler/__pycache__/handler.cpython-314.pyc",
        "cdk.out/manifest.json",
    ],
)
def test_unrelated_files_do_not_change_the_hash(workspace: Path, changed: str) -> None:
    before = fingerprint(workspace)
    edit(workspace, changed)
    assert fingerprint(workspace) == before
