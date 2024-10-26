# Use a Python image with uv pre-installed
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Install the project into `/app`
WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Install git
RUN apt-get update && apt-get install -y git

# Install the project's dependencies using the lockfile and settings
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Then, add the rest of the project source code and install it
ADD . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Clear installed packages
RUN apt-get purge -y git && apt-get autoremove -y && apt-get update && apt-get clean -y

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

ENV WORKERS=1
ENV PORT=80

# Reset the entrypoint, don't invoke `uv`
ENTRYPOINT []

CMD ["sh", "-c", "fastapi run src/lvmapi/app.py --port $PORT --workers $WORKERS"]
