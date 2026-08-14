# Image Processor

A serverless tool built with AWS for processing images for use with blogs or other websites where images need to be displayed

## Architecture

[Design Document](docs/design.md)

## Infrastructure

The AWS infrastructure is defined with Python CDK and includes separate stacks for
each deployment environment:

- `image-processor-infra-dev`
- `image-processor-infra-prod`

The development bucket and its contents are deleted when its stack is deleted.
The production bucket is retained.

### Prerequisites

- [uv](https://docs.astral.sh/uv/)
- [Node.js](https://nodejs.org/)
- [AWS CDK](https://docs.aws.amazon.com/cdk/v2/guide/cli.html)
- AWS credentials for the account and region where the stack will be deployed

### Bootstrap

Install the Python dependencies and bootstrap each target AWS account and region
once:

```bash
uv sync --frozen --dev
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
