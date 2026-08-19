FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY frontend ./frontend
COPY docs/templates ./docs/templates
COPY CHANGELOG.md MANUAL.md ./

# Baked-in fallback for the header version badge (GET /api/system/version)
# when there's no live git checkout at /app to `git describe` - e.g. a
# plain `docker run`/Portainer deployment straight from this image,
# without the docker-compose.yml bind-mount. Set from CI, see
# .github/workflows/docker-publish.yml.
ARG VERSION=unknown
ENV KNXPILOT_IMAGE_VERSION=$VERSION

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
