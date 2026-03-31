import subprocess

# Check SDK version in agent-runner image
r1 = subprocess.run(
    ['docker', 'run', '--rm', '--entrypoint', 'python3', 'agent-runner:latest', '-c',
     'import copilot; print("image SDK:", copilot.__version__ if hasattr(copilot,"__version__") else "no version"); import pkg_resources; print(pkg_resources.get_distribution("github-copilot-sdk").version)'],
    capture_output=True, text=True, timeout=15
)
print("Image SDK:", r1.stdout.strip(), r1.stderr[:100])

# Check SDK version in backend container
r2 = subprocess.run(
    ['python3', '-c',
     'import copilot; print("backend SDK:", copilot.__version__ if hasattr(copilot,"__version__") else "no version"); import pkg_resources; print(pkg_resources.get_distribution("github-copilot-sdk").version)'],
    capture_output=True, text=True, timeout=10
)
print("Backend SDK:", r2.stdout.strip(), r2.stderr[:100])

# Check create_session signature in image
r3 = subprocess.run(
    ['docker', 'run', '--rm', '--entrypoint', 'python3', 'agent-runner:latest', '-c',
     'import inspect; from copilot import CopilotClient; print(inspect.signature(CopilotClient.create_session))'],
    capture_output=True, text=True, timeout=15
)
print("create_session signature (image):", r3.stdout.strip())
