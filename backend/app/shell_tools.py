"""
Shell Tools — Read-only diagnostics and write-impacting operations.

Permission enforcement:
  execute_commands=False          → nothing allowed
  execute_commands=True
    allow_read_only_commands=True → diagnostics group only
    allow_write_impacting_commands=True → write group also allowed
"""

import subprocess
import platform
import os
import sys
import socket
from pathlib import Path

TIMEOUT = 15  # seconds for all subprocess calls


def _run(cmd: list[str], cwd: str | None = None) -> str:
    """Run a subprocess and return combined stdout+stderr, truncated to 4000 chars."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=TIMEOUT, cwd=cwd
        )
        out = (result.stdout or "") + (result.stderr or "")
        return out.strip()[:4000] or "(no output)"
    except subprocess.TimeoutExpired:
        return f"[Timeout] Command exceeded {TIMEOUT}s"
    except FileNotFoundError:
        return f"[Error] Command not found: {cmd[0]}"
    except Exception as e:
        return f"[Error] {e}"


def _is_windows() -> bool:
    return platform.system() == "Windows"

# ── A. Diagnostics / Read-only ────────────────────────────────────────────────

def get_system_info() -> str:
    lines = [
        f"OS:           {platform.system()} {platform.release()} {platform.version()}",
        f"Machine:      {platform.machine()}",
        f"Processor:    {platform.processor()}",
        f"Python:       {sys.version}",
        f"Hostname:     {socket.gethostname()}",
        f"CWD:          {os.getcwd()}",
    ]
    try:
        import psutil
        mem = psutil.virtual_memory()
        lines.append(f"RAM total:    {mem.total // (1024**3)} GB")
        lines.append(f"RAM used:     {mem.percent}%")
        cpu = psutil.cpu_percent(interval=0.5)
        lines.append(f"CPU usage:    {cpu}%")
    except ImportError:
        lines.append("(install psutil for memory/CPU stats)")
    return "\n".join(lines)


def get_runtime_versions() -> str:
    results = {}
    checks = {
        "python": [sys.executable, "--version"],
        "node":   ["node", "--version"],
        "npm":    ["npm", "--version"],
        "git":    ["git", "--version"],
        "docker": ["docker", "--version"],
        "pip":    [sys.executable, "-m", "pip", "--version"],
    }
    for name, cmd in checks.items():
        out = _run(cmd)
        results[name] = out.split("\n")[0] if out else "not found"
    return "\n".join(f"{k:10} {v}" for k, v in results.items())


def get_current_directory() -> str:
    return os.getcwd()


def get_environment_summary() -> str:
    safe_keys = {"PATH", "HOME", "USER", "USERNAME", "SHELL", "TERM",
                 "LANG", "LC_ALL", "VIRTUAL_ENV", "CONDA_DEFAULT_ENV",
                 "NODE_ENV", "PYTHONPATH", "JAVA_HOME", "GOPATH"}
    lines = [f"{k}={v}" for k, v in os.environ.items() if k in safe_keys]
    return "\n".join(sorted(lines)) or "(no relevant env vars found)"


def check_path_exists(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return f"Does not exist: {path}"
    kind = "directory" if p.is_dir() else "file"
    stat = p.stat()
    return f"Exists ({kind}): {path}\nSize: {stat.st_size} bytes\nModified: {stat.st_mtime}"


def get_file_metadata(path: str) -> str:
    return check_path_exists(path)


def search_files(root: str, pattern: str) -> str:
    """Glob search for files matching pattern under root."""
    base = Path(root)
    if not base.exists():
        return f"Error: path does not exist: {root}"
    matches = list(base.rglob(pattern))[:50]
    if not matches:
        return f"No files matching '{pattern}' found under {root}"
    return "\n".join(str(m.relative_to(base)) for m in matches)


def list_processes() -> str:
    if _is_windows():
        return _run(["tasklist"])
    return _run(["ps", "aux"])


def find_process(name: str) -> str:
    if _is_windows():
        return _run(["tasklist", "/FI", f"IMAGENAME eq {name}*"])
    return _run(["pgrep", "-la", name])


def get_process_details(pid: str) -> str:
    if _is_windows():
        return _run(["tasklist", "/FI", f"PID eq {pid}", "/V"])
    return _run(["ps", "-p", pid, "-f"])


def list_listening_ports() -> str:
    if _is_windows():
        return _run(["netstat", "-ano"])
    return _run(["ss", "-tlnp"])


def check_port_status(host: str, port: str) -> str:
    try:
        with socket.create_connection((host, int(port)), timeout=5):
            return f"Port {port} on {host} is OPEN"
    except (ConnectionRefusedError, OSError):
        return f"Port {port} on {host} is CLOSED or unreachable"
    except Exception as e:
        return f"Error checking port: {e}"


def check_dns_resolution(hostname: str) -> str:
    try:
        ip = socket.gethostbyname(hostname)
        return f"{hostname} resolves to {ip}"
    except socket.gaierror as e:
        return f"DNS resolution failed for {hostname}: {e}"


def check_http_endpoint(url: str) -> str:
    try:
        import httpx
        resp = httpx.get(url, timeout=10, follow_redirects=True)
        return f"HTTP {resp.status_code} — {url}\nContent-Type: {resp.headers.get('content-type', 'unknown')}"
    except Exception as e:
        return f"Error reaching {url}: {e}"


def test_host_reachability(host: str) -> str:
    flag = "-n" if _is_windows() else "-c"
    return _run(["ping", flag, "3", host])


def read_log_tail(path: str, lines: int = 50) -> str:
    p = Path(path)
    if not p.exists():
        return f"Error: log file not found: {path}"
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
        tail = content.splitlines()[-lines:]
        return "\n".join(tail)
    except Exception as e:
        return f"Error reading log: {e}"


def search_logs(path: str, keyword: str) -> str:
    p = Path(path)
    if not p.exists():
        return f"Error: log file not found: {path}"
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
        matches = [ln for ln in content.splitlines() if keyword.lower() in ln.lower()]
        return "\n".join(matches[:100]) if matches else f"No lines containing '{keyword}' found"
    except Exception as e:
        return f"Error searching log: {e}"


def read_recent_errors(path: str) -> str:
    return search_logs(path, "error")


def check_docker_status() -> str:
    return _run(["docker", "info"])


def list_containers() -> str:
    return _run(["docker", "ps", "-a"])


# ── B. Write-impacting operations ─────────────────────────────────────────────

def create_file(path: str, content: str = "") -> str:
    p = Path(path)
    if p.exists():
        return f"Error: file already exists: {path}. Use append_file or delete first."
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Created file: {path}"
    except Exception as e:
        return f"Error creating file: {e}"


def append_file(path: str, content: str) -> str:
    p = Path(path)
    if not p.exists():
        return f"Error: file not found: {path}"
    try:
        existing = p.read_text(encoding="utf-8")
        sep = "\n" if existing and not existing.endswith("\n") else ""
        p.write_text(existing + sep + content, encoding="utf-8")
        return f"Appended {len(content)} chars to {path}"
    except Exception as e:
        return f"Error appending: {e}"


def rename_file(src: str, dst: str) -> str:
    try:
        Path(src).rename(dst)
        return f"Renamed {src} → {dst}"
    except Exception as e:
        return f"Error renaming: {e}"


def delete_file(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return f"Error: not found: {path}"
    try:
        p.unlink()
        return f"Deleted file: {path}"
    except Exception as e:
        return f"Error deleting: {e}"


def create_directory(path: str) -> str:
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        return f"Created directory: {path}"
    except Exception as e:
        return f"Error creating directory: {e}"


def remove_directory(path: str) -> str:
    import shutil
    try:
        shutil.rmtree(path)
        return f"Removed directory: {path}"
    except Exception as e:
        return f"Error removing directory: {e}"


def start_process(command: str, cwd: str | None = None) -> str:
    try:
        proc = subprocess.Popen(
            command, shell=True, cwd=cwd,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        return f"Started process PID {proc.pid}: {command}"
    except Exception as e:
        return f"Error starting process: {e}"


def stop_process(pid: str) -> str:
    if _is_windows():
        return _run(["taskkill", "/PID", pid, "/F"])
    return _run(["kill", pid])


def restart_service(service: str) -> str:
    if _is_windows():
        out = _run(["net", "stop", service])
        out += "\n" + _run(["net", "start", service])
        return out
    return _run(["sudo", "systemctl", "restart", service])


def run_script(script_path: str, cwd: str | None = None) -> str:
    p = Path(script_path)
    if not p.exists():
        return f"Error: script not found: {script_path}"
    if p.suffix == ".py":
        return _run([sys.executable, script_path], cwd=cwd)
    if p.suffix in (".sh", ".bash"):
        return _run(["bash", script_path], cwd=cwd)
    if p.suffix in (".ps1",):
        return _run(["powershell", "-File", script_path], cwd=cwd)
    return _run([script_path], cwd=cwd)


def run_shell_command(command: str, cwd: str | None = None) -> str:
    if _is_windows():
        return _run(["cmd", "/c", command], cwd=cwd)
    return _run(["bash", "-c", command], cwd=cwd)


def install_package(package: str, manager: str = "pip") -> str:
    if manager == "pip":
        return _run([sys.executable, "-m", "pip", "install", package])
    if manager == "npm":
        return _run(["npm", "install", package])
    if manager == "apt":
        return _run(["sudo", "apt-get", "install", "-y", package])
    return f"Unknown package manager: {manager}"


def git_checkout(branch: str, cwd: str | None = None) -> str:
    return _run(["git", "checkout", branch], cwd=cwd)


def git_commit(message: str, cwd: str | None = None) -> str:
    _run(["git", "add", "-A"], cwd=cwd)
    return _run(["git", "commit", "-m", message], cwd=cwd)


def docker_start(container: str) -> str:
    return _run(["docker", "start", container])


def docker_stop(container: str) -> str:
    return _run(["docker", "stop", container])


# ── Permission-gated tool builder ─────────────────────────────────────────────

# Maps tool name → (function, description, parameters_schema)
_READONLY_TOOLS: dict[str, tuple] = {
    "get_system_info": (get_system_info, "Get OS, CPU, RAM, Python version and hostname.", {}),
    "get_runtime_versions": (get_runtime_versions, "Get installed versions of python, node, npm, git, docker.", {}),
    "get_current_directory": (get_current_directory, "Get the current working directory of the server process.", {}),
    "get_environment_summary": (get_environment_summary, "Get safe environment variables (PATH, VIRTUAL_ENV, etc.).", {}),
    "check_path_exists": (check_path_exists, "Check if a file or directory exists and get its metadata.", {"path": ("string", "Absolute or relative path to check")}),
    "get_file_metadata": (get_file_metadata, "Get size and modification time of a file or directory.", {"path": ("string", "Path to inspect")}),
    "search_files": (search_files, "Search for files matching a glob pattern under a root directory.", {"root": ("string", "Root directory to search"), "pattern": ("string", "Glob pattern e.g. '*.py' or '**/*.log'")}),
    "list_processes": (list_processes, "List all running processes.", {}),
    "find_process": (find_process, "Find processes by name.", {"name": ("string", "Process name to search for")}),
    "get_process_details": (get_process_details, "Get details of a process by PID.", {"pid": ("string", "Process ID")}),
    "list_listening_ports": (list_listening_ports, "List all ports currently listening for connections.", {}),
    "check_port_status": (check_port_status, "Check if a TCP port is open on a host.", {"host": ("string", "Hostname or IP"), "port": ("string", "Port number")}),
    "check_dns_resolution": (check_dns_resolution, "Resolve a hostname to an IP address.", {"hostname": ("string", "Hostname to resolve")}),
    "check_http_endpoint": (check_http_endpoint, "Send a GET request and return the HTTP status.", {"url": ("string", "Full URL to check")}),
    "test_host_reachability": (test_host_reachability, "Ping a host to test network reachability.", {"host": ("string", "Hostname or IP to ping")}),
    "read_log_tail": (read_log_tail, "Read the last N lines of a log file.", {"path": ("string", "Path to log file"), "lines": ("integer", "Number of lines to read (default 50)")}),
    "search_logs": (search_logs, "Search a log file for lines containing a keyword.", {"path": ("string", "Path to log file"), "keyword": ("string", "Keyword to search for")}),
    "read_recent_errors": (read_recent_errors, "Read lines containing 'error' from a log file.", {"path": ("string", "Path to log file")}),
    "check_docker_status": (check_docker_status, "Get Docker daemon status and info.", {}),
    "list_containers": (list_containers, "List all Docker containers.", {}),
}

_WRITE_TOOLS: dict[str, tuple] = {
    "create_file": (create_file, "Create a new file with optional content.", {"path": ("string", "File path to create"), "content": ("string", "Initial file content (optional)")}),
    "append_file": (append_file, "Append content to the end of an existing file.", {"path": ("string", "File path"), "content": ("string", "Content to append")}),
    "rename_file": (rename_file, "Rename or move a file.", {"src": ("string", "Source path"), "dst": ("string", "Destination path")}),
    "delete_file": (delete_file, "Delete a file.", {"path": ("string", "File path to delete")}),
    "create_directory": (create_directory, "Create a directory (and parents).", {"path": ("string", "Directory path to create")}),
    "remove_directory": (remove_directory, "Remove a directory and all its contents.", {"path": ("string", "Directory path to remove")}),
    "start_process": (start_process, "Start a process or command in the background.", {"command": ("string", "Shell command to run"), "cwd": ("string", "Working directory (optional)")}),
    "stop_process": (stop_process, "Stop a process by PID.", {"pid": ("string", "Process ID to stop")}),
    "restart_service": (restart_service, "Restart a system service.", {"service": ("string", "Service name")}),
    "run_script": (run_script, "Run a script file (.py, .sh, .ps1).", {"script_path": ("string", "Path to script"), "cwd": ("string", "Working directory (optional)")}),
    "run_shell_command": (run_shell_command, "Run an arbitrary shell command.", {"command": ("string", "Command to execute"), "cwd": ("string", "Working directory (optional)")}),
    "install_package": (install_package, "Install a package via pip, npm, or apt.", {"package": ("string", "Package name"), "manager": ("string", "Package manager: pip | npm | apt")}),
    "git_checkout": (git_checkout, "Checkout a git branch.", {"branch": ("string", "Branch name"), "cwd": ("string", "Repo directory (optional)")}),
    "git_commit": (git_commit, "Stage all changes and create a git commit.", {"message": ("string", "Commit message"), "cwd": ("string", "Repo directory (optional)")}),
    "docker_start": (docker_start, "Start a Docker container.", {"container": ("string", "Container name or ID")}),
    "docker_stop": (docker_stop, "Stop a Docker container.", {"container": ("string", "Container name or ID")}),
}


def _make_tool_def(name: str, description: str, params: dict) -> dict:
    properties = {}
    required = []
    for param_name, (param_type, param_desc) in params.items():
        properties[param_name] = {"type": param_type, "description": param_desc}
        if param_name not in ("cwd", "content", "lines"):  # optional params
            required.append(param_name)
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def build_shell_tools(shell_permissions: dict) -> list[dict]:
    """
    Build tool definitions based on granted shell permissions.
    shell_permissions = {
        "execute_commands": bool,
        "allow_read_only_commands": bool,
        "allow_write_impacting_commands": bool,
    }
    """
    if not shell_permissions.get("execute_commands", False):
        return []

    tools = []
    if shell_permissions.get("allow_read_only_commands", False):
        for name, (_, desc, params) in _READONLY_TOOLS.items():
            tools.append(_make_tool_def(name, desc, params))

    if shell_permissions.get("allow_write_impacting_commands", False):
        for name, (_, desc, params) in _WRITE_TOOLS.items():
            tools.append(_make_tool_def(name, desc, params))

    return tools


def dispatch_shell_tool(name: str, args: dict) -> str:
    """Execute a shell tool call by name."""
    if name in _READONLY_TOOLS:
        fn = _READONLY_TOOLS[name][0]
    elif name in _WRITE_TOOLS:
        fn = _WRITE_TOOLS[name][0]
    else:
        return f"Unknown shell tool: {name}"
    try:
        return fn(**{k: v for k, v in args.items() if v is not None})
    except TypeError as e:
        return f"Error calling {name}: {e}"
