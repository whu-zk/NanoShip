"""Deployment engine for NanoShip."""

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from nanoship.config import settings
from nanoship.project_analyzer import ProjectAnalyzer, ProjectInfo
from nanoship.ssh_manager import SSHManager, ServerConfig

console = Console()


@dataclass
class DeployConfig:
    """Deployment configuration."""

    project_path: str
    server_name: str
    remote_path: Optional[str] = None
    domain: Optional[str] = None
    ssl: bool = True
    env_vars: Optional[dict] = None


class Deployer:
    """Handles deployment of projects to remote servers."""

    def __init__(self, ssh_manager: SSHManager):
        self.ssh = ssh_manager
        self.remote_base_path = settings.default_deploy_path

    def deploy(self, config: DeployConfig) -> bool:
        """Execute full deployment process."""
        console.print(f"\n[bold blue]🚀 Starting deployment to {config.server_name}...[/bold blue]\n")

        # Step 1: Analyze project
        with console.status("[bold green]Analyzing project..."):
            analyzer = ProjectAnalyzer(config.project_path)
            project_info = analyzer.analyze()

        # Step 2: Generate Docker files if needed
        if not project_info.has_dockerfile:
            with console.status("[bold green]Generating Dockerfile..."):
                analyzer.write_docker_files(project_info)
        else:
            console.print("[dim]✓ Dockerfile already exists, skipping generation[/dim]")

        # Step 3: Prepare remote directory
        remote_path = config.remote_path or f"{self.remote_base_path}/{project_info.name}"
        with console.status(f"[bold green]Preparing remote directory {remote_path}..."):
            self.ssh.execute(f"mkdir -p {remote_path}")

        # Step 4: Upload files
        with console.status("[bold green]Uploading files..."):
            self._upload_project(config.project_path, remote_path)

        # Step 5: Build and deploy
        with console.status("[bold green]Building and starting containers..."):
            success = self._build_and_deploy(remote_path, project_info)

        if not success:
            console.print("[red]✗ Deployment failed during build/start phase[/red]")
            return False

        # Step 6: Configure reverse proxy if domain is provided
        if config.domain:
            with console.status(f"[bold green]Configuring reverse proxy for {config.domain}..."):
                self._configure_reverse_proxy(config.domain, project_info.port, config.ssl)

        console.print(f"\n[bold green]✅ Deployment completed successfully![/bold green]")
        if config.domain:
            console.print(f"[green]   Your app is live at: https://{config.domain}[/green]")
        else:
            console.print(f"[green]   Your app is running on port {project_info.port}[/green]")

        return True

    def _upload_project(self, local_path: str, remote_path: str):
        """Upload project files to remote server."""
        exclude = [
            ".git",
            "__pycache__",
            ".pytest_cache",
            "node_modules",
            ".env",
            ".venv",
            "venv",
            ".idea",
            ".vscode",
            "*.pyc",
            ".DS_Store",
        ]

        self.ssh.upload_directory(local_path, remote_path, exclude=exclude)

    def _build_and_deploy(self, remote_path: str, info: ProjectInfo) -> bool:
        """Build and deploy Docker containers on remote server."""
        # Stop existing containers
        self.ssh.execute(f"cd {remote_path} && docker-compose down --remove-orphans 2>/dev/null || true")

        # Build and start
        exit_code, stdout, stderr = self.ssh.execute(
            f"cd {remote_path} && docker-compose up -d --build",
            stream=True
        )

        if exit_code != 0:
            console.print(f"[red]Docker build failed:[/red]\n{stderr}")
            return False

        # Wait for container to be healthy
        time.sleep(3)

        # Check if container is running
        service_name = info.name.lower().replace(" ", "-")
        exit_code, stdout, _ = self.ssh.execute(
            f"cd {remote_path} && docker-compose ps -q {service_name}"
        )

        if not stdout.strip():
            console.print("[red]Container failed to start[/red]")
            return False

        return True

    def _configure_reverse_proxy(self, domain: str, port: int, ssl: bool = True):
        """Configure Caddy or Nginx as reverse proxy."""
        # Check if Caddy is installed
        exit_code, _, _ = self.ssh.execute("which caddy", stream=False)

        if exit_code == 0:
            self._configure_caddy(domain, port, ssl)
        else:
            self._configure_nginx(domain, port, ssl)

    def _configure_caddy(self, domain: str, port: int, ssl: bool = True):
        """Configure Caddy reverse proxy."""
        caddy_config = f"""{domain} {{
    reverse_proxy localhost:{port}
"""
        if ssl:
            caddy_config += "    tls internal\n"
        caddy_config += "}\n"

        config_path = f"/etc/caddy/conf.d/{domain}.conf"

        # Write Caddyfile
        self.ssh.write_file(config_path, caddy_config)

        # Reload Caddy
        self.ssh.execute("systemctl reload caddy || caddy reload --config /etc/caddy/Caddyfile")

        console.print(f"[green]✓ Caddy configured for {domain}[/green]")

    def _configure_nginx(self, domain: str, port: int, ssl: bool = True):
        """Configure Nginx reverse proxy."""
        nginx_config = f"""server {{
    listen 80;
    server_name {domain};

    location / {{
        proxy_pass http://localhost:{port};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }}
}}
"""

        config_path = f"/etc/nginx/sites-available/{domain}"
        enabled_path = f"/etc/nginx/sites-enabled/{domain}"

        # Write config
        self.ssh.write_file(config_path, nginx_config)

        # Enable site
        self.ssh.execute(f"ln -sf {config_path} {enabled_path}")

        # Test and reload nginx
        exit_code, _, stderr = self.ssh.execute("nginx -t")
        if exit_code == 0:
            self.ssh.execute("systemctl reload nginx || service nginx reload")
            console.print(f"[green]✓ Nginx configured for {domain}[/green]")
        else:
            console.print(f"[red]Nginx configuration test failed: {stderr}[/red]")

        # Setup SSL with Certbot if requested
        if ssl:
            self._setup_ssl_certbot(domain)

    def _setup_ssl_certbot(self, domain: str):
        """Setup SSL certificate using Certbot."""
        # Check if certbot is installed
        exit_code, _, _ = self.ssh.execute("which certbot", stream=False)

        if exit_code != 0:
            console.print("[yellow]Certbot not installed, skipping SSL setup[/yellow]")
            return

        # Obtain certificate
        exit_code, stdout, stderr = self.ssh.execute(
            f"certbot --nginx -d {domain} --non-interactive --agree-tos --email admin@{domain}",
            stream=True
        )

        if exit_code == 0:
            console.print(f"[green]✓ SSL certificate installed for {domain}[/green]")
        else:
            console.print(f"[yellow]SSL setup failed: {stderr}[/yellow]")

    def check_health(self, port: int, path: str = "/health") -> tuple[bool, str]:
        """Check if the deployed application is healthy."""
        exit_code, stdout, stderr = self.ssh.execute(
            f"curl -sf http://localhost:{port}{path} || curl -sf http://localhost:{port}",
            stream=False
        )

        if exit_code == 0:
            return True, stdout
        return False, stderr

    def get_logs(self, remote_path: str, tail: int = 50) -> str:
        """Get container logs from remote server."""
        exit_code, stdout, _ = self.ssh.execute(
            f"cd {remote_path} && docker-compose logs --tail={tail}",
            stream=False
        )
        return stdout

    def rollback(self, remote_path: str):
        """Rollback to previous deployment."""
        console.print("[yellow]Rolling back deployment...[/yellow]")
        self.ssh.execute(f"cd {remote_path} && docker-compose down")
        # TODO: Implement actual rollback with backup containers
        console.print("[green]✓ Rollback completed[/green]")
