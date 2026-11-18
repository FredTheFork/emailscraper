FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HARVESTER_DB_PATH=/app/data/window_websites.db \
    HARVESTER_OUTPUT_DIR=/app/output

WORKDIR /app

COPY pyproject.toml requirements.txt README.md harvest.py ./
COPY window_harvester ./window_harvester

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e . && \
    mkdir -p /app/data /app/output

VOLUME ["/app/data", "/app/output"]

ENTRYPOINT ["window-harvester"]
CMD ["run", "--preset", "free-max", "--export"]
