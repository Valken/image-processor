# Image Processor

A serverless tool built with AWS for processing images for use with blogs or other websites where images need to be displayed

## Architecture

[Design Document](docs/design.md)

## Infrastructure

The AWS infrastructure is defined with Python CDK as two stacks per
environment, split by whether their resources hold state:

| Stack | Contents | Changes |
|---|---|---|
| `image-processor-infra-{env}` | **Stateful:** S3 bucket, CloudFront, SQS upload queue + DLQ, EventBridge upload rule | Rarely |
| `image-processor-service-{env}` | **Stateless:** Lambdas and their IAM grants | Every deploy |

References only flow from the service stack to the infra stack. Grant
permissions on the Lambda's own role (`bucket.grant_*(fn)`,
`fn.add_event_source(...)`); never edit a stateful resource's policy to name
something in the service stack, or the stacks form a dependency cycle.

In dev, stateful resources (and the bucket's contents) are deleted with their
stack. In prod they are retained, and the infra stack has termination
protection. CloudFormation replaces a resource when its logical ID changes, so
`tests/cdk/test_infra_stack.py` pins the stateful resources' logical IDs.

### Lambda packaging

Each Lambda handler is its own uv workspace member under `handlers/<name>/`,
with a flat-layout package and its own runtime dependencies. Tests live in the
root `tests/` tree:

```
handlers/hello/
  pyproject.toml            # name = "hello-handler"
  hello_handler/
    __init__.py
    handler.py
tests/
  handlers/test_hello.py
  cdk/test_infra_stack.py
```

All members share the single root `uv.lock`. In CDK, the `UvPythonFunction`
construct (`cdk/uv_python_function.py`) bundles a member as a ZIP asset using
`cdk/bundling/Dockerfile`, a Linux AMD64 SAM build image. It installs the
member and only its locked runtime dependencies directly into the asset (no
virtualenv):

```bash
uv export --frozen --no-dev --package hello-handler --no-editable --no-hashes \
  | uv pip install --no-deps --target <asset-output> -r -
```

Each function's asset hash is derived only from the root `pyproject.toml`,
`uv.lock`, the members' `pyproject.toml` files and that handler's own source,
so changes to other handlers, CDK code, tests, IDE files or `cdk.out` don't
redeploy it.

#### Adding a handler

1. Create `handlers/<name>/` with a `pyproject.toml` (copy `handlers/hello`'s)
   and a `<package>/` directory beside it, then add tests under
   `tests/handlers/`.
2. Run `uv lock && uv sync --all-packages`.
3. Add it to a stack:

   ```python
   UvPythonFunction(
       self,
       "ResizeFunction",
       path="handlers/resize",
       handler="resize_handler.handler.handler",
   )
   ```

The deployed hello-world Lambda has no trigger yet. Connecting the image
processor to the SQS queue is deferred until its processing behavior is
implemented.

### Prerequisites

- [uv](https://docs.astral.sh/uv/)
- [Node.js](https://nodejs.org/)
- [AWS CDK](https://docs.aws.amazon.com/cdk/v2/guide/cli.html)
- AWS credentials for the account and region where the stack will be deployed

### Bootstrap

Install the Python dependencies and bootstrap each target AWS account and region
once:

```bash
uv sync --frozen --dev --all-packages
cdk bootstrap aws://$AWS_ACCOUNT_ID/$AWS_REGION
```

### Synthesize

Run either command from the repository root:

```bash
(cd cdk && uv run cdk synth --context environment=dev)
(cd cdk && uv run cdk synth --context environment=prod)
```

### Deploy

Deployments are intentionally manual. Run the matching command for the intended
environment:

```bash
(cd cdk && uv run cdk deploy --context environment=dev)
(cd cdk && uv run cdk deploy --context environment=prod)
```

### Releases

Pushes to `main` are tracked by [release-please](https://github.com/googleapis/release-please),
which keeps a release pull request up to date with a generated `CHANGELOG.md` entry
and version bump based on [Conventional Commits](https://www.conventionalcommits.org/).
Merging that pull request creates a GitHub release and a `vX.Y.Z` tag, which
automatically deploys the `dev` environment via GitHub Actions.

`prod` deploys remain a deliberate action — either run the `Deploy` workflow
manually from the Actions tab with `environment: prod`, or check out the
release tag and deploy locally:

```bash
git fetch --tags
git checkout vX.Y.Z
(cd cdk && uv run cdk deploy --context environment=prod)
```
