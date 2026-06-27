FROM python:3.12-slim

LABEL org.opencontainers.image.title="gddynu" \
      org.opencontainers.image.description="Dynu dynamic DNS updater with IP change logging" \
      org.opencontainers.image.licenses="GPL-3.0-or-later"

WORKDIR /app

# Install the package (no runtime dependencies — stdlib only).
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir .

# Persist state + IP log here; mount a volume to keep them across restarts.
ENV GDDYNU_STATE_FILE=/data/gddynu-state.json \
    GDDYNU_LOG_FILE=/data/gddynu-logs.jsonl
VOLUME ["/data"]

# Daemon mode by default. Configure via GDDYNU_* env vars (see README), or mount
# a config file and override the command with `--config /config/gddynu.toml`.
ENTRYPOINT ["python", "-m", "gddynu"]
CMD ["--daemon"]
