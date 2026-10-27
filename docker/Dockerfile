# MCP-IDS lab image. One image runs the agent, (later) proxies, and all stdio
# MCP servers as child processes. See ARCHITECTURE.md "Why one lab container".
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Unprivileged user: nothing in the lab runs as root.
RUN useradd --create-home --uid 10001 lab && mkdir /lab && chown lab:lab /lab
WORKDIR /lab

COPY requirements.txt .
RUN pip install -r requirements.txt

# CPU-only PyTorch for the CNN comes from its own index (see requirements-torch.txt), in a
# separate step. If docker/wheels/ holds pre-downloaded Linux wheels (docker/wheels/README.txt),
# it installs offline from them: useful when downloads inside Docker are slow or blocked.
# The folder is mounted only for this step, so the wheels never end up in the image.
COPY requirements-torch.txt .
RUN --mount=type=bind,from=wheels,target=/tmp/wheels \
    if ls /tmp/wheels/torch-*.whl >/dev/null 2>&1; then \
        pip install --no-index --find-links /tmp/wheels -r requirements-torch.txt; \
    else \
        pip install -r requirements-torch.txt; \
    fi

COPY --chown=lab:lab . .
USER lab

# The sandbox lives inside the container (copied from the repo's seed data),
# so writes by the filesystem server never touch the host.
ENV MCP_FS_SANDBOX=/lab/sandbox \
    PYTHONPATH=/lab

CMD ["python", "-m", "pytest", "-v"]
