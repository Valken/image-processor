FROM ghcr.io/astral-sh/uv:0.7.13 AS uv

FROM public.ecr.aws/sam/build-python3.14

COPY --from=uv /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_NO_PROGRESS=1 \
    UV_PYTHON_DOWNLOADS=never

# Make compiled bytecode deterministic (hash-based .pyc instead of mtime-based)
# so repeated bundles of unchanged code produce identical asset hashes.
ENV SOURCE_DATE_EPOCH=0
