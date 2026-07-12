FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN useradd --create-home --shell /bin/bash recall

COPY pyproject.toml README.md /app/
COPY src /app/src

RUN pip install --upgrade pip && pip install .

RUN mkdir -p /data && chown -R recall:recall /app /data

USER recall

CMD ["uvicorn", "recall.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
