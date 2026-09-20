FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .

RUN pip wheel \
    --no-cache-dir \
    --wheel-dir /wheels \
    -r requirements.txt


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN groupadd --system app \
    && useradd \
        --system \
        --gid app \
        --create-home \
        app

WORKDIR /app

COPY --from=builder /wheels /wheels

RUN pip install \
    --no-cache-dir \
    /wheels/* \
    && rm -rf /wheels

COPY app ./app

RUN chown -R app:app /app

USER app

EXPOSE 8000

CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]