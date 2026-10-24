FROM python:3.13-slim

# git is required for discovery metadata and WIP triage (diff / commit / discard).
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir .

# Persist the event store and mount your code under /projects.
ENV DCP_DB_PATH=/data/context_fabric.db \
    DCP_SCAN_ROOT=/projects
VOLUME ["/data", "/projects"]

EXPOSE 8787
# 0.0.0.0 is required inside the container; publish the port to 127.0.0.1 on the host.
CMD ["dcp", "--host", "0.0.0.0", "--port", "8787"]
