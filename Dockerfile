
FROM python:3.11-slim-bookworm


ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install required system dependencies INCLUDING postgres client
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy uv binary (fast installer)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install Python dependencies (layer cached)
COPY Django_restaurant_api/requirements.txt .

RUN uv pip install --system --no-cache -r requirements.txt
# RUN pip install --no-cache-dir -r requirements.txt
# Copy project files
COPY Django_restaurant_api/ .

EXPOSE 8000

CMD ["./entrypoint.sh"]
