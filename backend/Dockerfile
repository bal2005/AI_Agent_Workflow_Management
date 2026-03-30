FROM python:3.11-slim

# Install Redis, supervisor, and Docker CLI
# Docker CLI lets the backend spawn sandbox containers via the mounted socket
RUN apt-get update && apt-get install -y \
    redis-server \
    supervisor \
    curl \
    ca-certificates \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
    && chmod a+r /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
       https://download.docker.com/linux/debian bookworm stable" \
       > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .
# Use the docker-specific env (Redis points to 127.0.0.1 inside container)
RUN cp .env.docker .env

# Supervisor config
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Create log dir
RUN mkdir -p /var/log/supervisor

EXPOSE 8000

CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
