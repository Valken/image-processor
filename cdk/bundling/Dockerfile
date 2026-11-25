FROM ghcr.io/astral-sh/uv:0.13.10 AS uv

FROM public.ecr.aws/sam/build-python3.14

# The SAM image ships its own uv binaries (/root/.local/bin, /var/lang/bin)
# ahead of /bin on PATH, and CDK runs bundling as the host user, so the
# unpinned /var/lang/bin/uv would win. Put the pinned uv first. Keep this
# version in step with [tool.uv] required-version in pyproject.toml.
COPY --from=uv /uv /uvx /opt/uv/bin/
ENV PATH=/opt/uv/bin:$PATH

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_NO_PROGRESS=1 \
    UV_PYTHON_DOWNLOADS=never

# Make compiled bytecode deterministic (hash-based .pyc instead of mtime-based)
# so repeated bundles of unchanged code produce identical asset hashes.
ENV SOURCE_DATE_EPOCH=0
