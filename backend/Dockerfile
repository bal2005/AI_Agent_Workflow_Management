FROM python:3.11-slim

# Install Redis + supervisor (process manager)
RUN apt-get update && apt-get install -y \
    redis-server \
    supervisor \
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
