# Dockerfile for the sandbox agent runner image.
# Build: docker build -f agent_runner.Dockerfile -t agent-runner:latest .
# This image runs inside the sandbox container — it has no access to the
# host filesystem except /workspace which is mounted per-run.

FROM python:3.11-slim

WORKDIR /app

# Only install what the agent runner needs
RUN pip install --no-cache-dir httpx cryptography github-copilot-sdk tavily-python

# Copy only the agent runner module
COPY app/sandbox/agent_runner.py /app/agent_runner.py

# Run as non-root for extra isolation
RUN useradd -m runner
USER runner

# Entrypoint: reads /workspace/.task_input.json, writes /workspace/.task_output.json
CMD ["python3", "/app/agent_runner.py"]
