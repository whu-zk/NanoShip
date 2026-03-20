"""SSH connection and command execution management."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import paramiko
from rich.console import Console

console = Console()


@dataclass
class ServerConfig:
    """Server configuration for SSH connection."""

    name: str
    host: str
    port: int = 22
    username: str = "root"
    password: Optional[str] = None
    key_path: Optional[str] = None
    key_content: Optional[str] = None


class SSHManager:
    """Manages SSH connections and remote command execution."""

    def __init__(self, server: ServerConfig):
        self.server = server
        self.client: Optional[paramiko.SSHClient] = None
        self.sftp: Optional[paramiko.SFTPClient] = None

    def connect(self) -> bool:
        """Establish SSH connection to the server."""
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            connect_kwargs = {
                "hostname": self.server.host,
                "port": self.server.port,
                "username": self.server.username,
                "timeout": 30,
            }

            # Priority: key_content > key_path > password
            if self.server.key_content:
                key_file = paramiko.RSAKey.from_private_key(
                    file_obj=__import__("io").StringIO(self.server.key_content)
                )
                connect_kwargs["pkey"] = key_file
            elif self.server.key_path:
                key_path = Path(self.server.key_path).expanduser()
                if key_path.exists():
                    connect_kwargs["key_filename"] = str(key_path)
                else:
                    console.print(f"[yellow]Warning: SSH key not found at {key_path}[/yellow]")

            if self.server.password and "pkey" not in connect_kwargs and "key_filename" not in connect_kwargs:
                connect_kwargs["password"] = self.server.password

            self.client.connect(**connect_kwargs)
            self.sftp = self.client.open_sftp()
            console.print(f"[green]✓ Connected to {self.server.name} ({self.server.host})[/green]")
            return True

        except Exception as e:
            console.print(f"[red]✗ Failed to connect to {self.server.name}: {e}[/red]")
            return False

    def disconnect(self):
        """Close SSH connection."""
        if self.sftp:
            self.sftp.close()
            self.sftp = None
        if self.client:
            self.client.close()
            self.client = None

    def execute(self, command: str, sudo: bool = False, stream: bool = True) -> tuple[int, str, str]:
        """Execute a command on the remote server.

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        if not self.client:
            raise RuntimeError("SSH connection not established")

        if sudo and self.server.username != "root":
            command = f"sudo {command}"

        stdin, stdout, stderr = self.client.exec_command(command)

        if stream:
            out_lines = []
            err_lines = []

            # Stream output in real-time
            while not stdout.channel.exit_status_ready():
                if stdout.channel.recv_ready():
                    line = stdout.readline()
                    if line:
                        out_lines.append(line)
                        console.print(f"[dim]{line.rstrip()}[/dim]")

                if stderr.channel.recv_stderr_ready():
                    line = stderr.readline()
                    if line:
                        err_lines.append(line)
                        console.print(f"[red]{line.rstrip()}[/red]")

            # Get remaining output
            out_lines.extend(stdout.readlines())
            err_lines.extend(stderr.readlines())

            exit_code = stdout.channel.recv_exit_status()
            return exit_code, "".join(out_lines), "".join(err_lines)
        else:
            exit_code = stdout.channel.recv_exit_status()
            return exit_code, stdout.read().decode(), stderr.read().decode()

    def upload_file(self, local_path: str, remote_path: str):
        """Upload a file to the remote server."""
        if not self.sftp:
            raise RuntimeError("SFTP connection not established")

        # Ensure remote directory exists
        remote_dir = os.path.dirname(remote_path)
        self.execute(f"mkdir -p {remote_dir}")

        self.sftp.put(local_path, remote_path)
        console.print(f"[dim]Uploaded {local_path} → {remote_path}[/dim]")

    def upload_directory(self, local_dir: str, remote_dir: str, exclude: Optional[list] = None):
        """Upload a directory to the remote server."""
        if not self.sftp:
            raise RuntimeError("SFTP connection not established")

        exclude = exclude or [".git", "__pycache__", ".pytest_cache", "node_modules", ".env"]
        local_path = Path(local_dir)

        for item in local_path.rglob("*"):
            if any(ex in str(item) for ex in exclude):
                continue

            if item.is_file():
                relative_path = item.relative_to(local_path)
                remote_file = f"{remote_dir}/{relative_path}".replace("\\", "/")
                remote_parent = os.path.dirname(remote_file)

                self.execute(f"mkdir -p {remote_parent}")
                self.sftp.put(str(item), remote_file)

        console.print(f"[dim]Uploaded directory {local_dir} → {remote_dir}[/dim]")

    def download_file(self, remote_path: str, local_path: str):
        """Download a file from the remote server."""
        if not self.sftp:
            raise RuntimeError("SFTP connection not established")

        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        self.sftp.get(remote_path, local_path)

    def file_exists(self, remote_path: str) -> bool:
        """Check if a file exists on the remote server."""
        try:
            self.sftp.stat(remote_path)
            return True
        except FileNotFoundError:
            return False

    def read_file(self, remote_path: str) -> str:
        """Read a file from the remote server."""
        if not self.sftp:
            raise RuntimeError("SFTP connection not established")

        with self.sftp.file(remote_path, "r") as f:
            return f.read().decode()

    def write_file(self, remote_path: str, content: str):
        """Write content to a file on the remote server."""
        if not self.sftp:
            raise RuntimeError("SFTP connection not established")

        # Ensure directory exists
        remote_dir = os.path.dirname(remote_path)
        self.execute(f"mkdir -p {remote_dir}")

        with self.sftp.file(remote_path, "w") as f:
            f.write(content.encode())

        console.print(f"[dim]Wrote {remote_path}[/dim]")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False
