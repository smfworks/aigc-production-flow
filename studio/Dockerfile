FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --no-cache-dir ".[celery,oidc]"

ENV STUDIO_DATABASE_URL=sqlite:////data/studio.db
ENV STUDIO_MEDIA_ROOT=/data/media
# No API token in the image. Listen on loopback unless the operator opts in.
ENV STUDIO_BIND_HOST=127.0.0.1

RUN mkdir -p /data/media
EXPOSE 8000
CMD ["python", "-m", "app.serve"]
