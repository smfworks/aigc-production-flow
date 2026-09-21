FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --no-cache-dir ".[celery,oidc]"

ENV STUDIO_DATABASE_URL=sqlite:////data/studio.db
ENV STUDIO_MEDIA_ROOT=/data/media
ENV STUDIO_API_TOKEN=local-dev-token

RUN mkdir -p /data/media
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
