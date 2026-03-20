"""Monitoring and alerting module for NanoShip."""

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import requests
from rich.console import Console

from nanoship.ai_engine import AIEngine
from nanoship.config import settings
from nanoship.database import db
from nanoship.ssh_manager import SSHManager

console = Console()


@dataclass
class HealthStatus:
    """Health check result."""

    healthy: bool
    status_code: int
    response_time: float
    error_message: Optional[str] = None


class Monitor:
    """Application monitoring and alerting."""

    def __init__(self, server, project_name: str, domain: Optional[str] = None, port: Optional[int] = None):
        self.server = server
        self.project_name = project_name
        self.domain = domain
        self.port = port
        self.ai = AIEngine()

    def check_health(self, path: str = "/health") -> HealthStatus:
        """Check application health via HTTP."""
        start_time = time.time()

        try:
            # Determine URL
            if self.domain:
                url = f"http://{self.domain}{path}"
            elif self.port:
                # Use SSH tunnel or direct check on server
                ssh = SSHManager(self.server)
                if not ssh.connect():
                    return HealthStatus(False, 0, 0, "SSH connection failed")

                try:
                    exit_code, stdout, _ = ssh.execute(
                        f"curl -sf -w '%{{http_code}}' http://localhost:{self.port}{path} -o /dev/null",
                        stream=False
                    )
                    response_time = time.time() - start_time

                    if exit_code == 0 and stdout.strip() == "200":
                        return HealthStatus(True, 200, response_time)
                    else:
                        # Try root path
                        exit_code, stdout, _ = ssh.execute(
                            f"curl -sf -w '%{{http_code}}' http://localhost:{self.port} -o /dev/null",
                            stream=False
                        )
                        if exit_code == 0:
                            return HealthStatus(True, int(stdout.strip()), response_time)
                        else:
                            return HealthStatus(False, 0, response_time, "Health check failed")
                finally:
                    ssh.disconnect()
            else:
                return HealthStatus(False, 0, 0, "No domain or port specified")

        except Exception as e:
            return HealthStatus(False, 0, time.time() - start_time, str(e))

    def get_logs(self, lines: int = 50) -> str:
        """Get recent container logs."""
        ssh = SSHManager(self.server)
        if not ssh.connect():
            return "Failed to connect to server"

        try:
            remote_path = f"/opt/nanoship/{self.project_name}"
            exit_code, stdout, _ = ssh.execute(
                f"cd {remote_path} && docker-compose logs --tail={lines}",
                stream=False
            )
            return stdout if exit_code == 0 else "Failed to retrieve logs"
        finally:
            ssh.disconnect()

    def analyze_and_alert(self, logs: str, health_status: HealthStatus) -> dict:
        """Analyze logs and send alerts if needed."""
        # Use AI to analyze logs
        analysis = self.ai.analyze_logs(logs, self.project_name)

        if analysis.get("issue_detected") or not health_status.healthy:
            self._send_alert(analysis, health_status)

        return analysis

    def _send_alert(self, analysis: dict, health_status: HealthStatus):
        """Send notification alert."""
        if not settings.webhook_url:
            console.print("[yellow]No webhook configured, skipping alert[/yellow]")
            return

        severity = analysis.get("severity", "warning")
        root_cause = analysis.get("root_cause", "Unknown issue")
        suggested_fix = analysis.get("suggested_fix", "No fix suggested")

        message = f"""🚨 NanoShip Alert

Project: {self.project_name}
Server: {self.server.name}
Severity: {severity.upper()}
Status: {'DOWN' if not health_status.healthy else 'DEGRADED'}

**Issue:**
{root_cause}

**Suggested Fix:**
{suggested_fix}

**Response Time:** {health_status.response_time:.2f}s
**Time:** {datetime.now().isoformat()}
"""

        try:
            if settings.webhook_type == "slack":
                payload = {
                    "text": message,
                    "attachments": [{
                        "color": "danger" if severity == "critical" else "warning",
                        "fields": [
                            {"title": "Project", "value": self.project_name, "short": True},
                            {"title": "Server", "value": self.server.name, "short": True},
                        ]
                    }]
                }
            elif settings.webhook_type == "discord":
                payload = {
                    "content": message,
                }
            else:
                payload = {"message": message}

            response = requests.post(settings.webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            console.print("[green]✓ Alert sent[/green]")

        except Exception as e:
            console.print(f"[red]Failed to send alert: {e}[/red]")

    def run_check(self) -> bool:
        """Run a full health check cycle."""
        console.print(f"[blue]Checking health of {self.project_name}...[/blue]")

        # Check health
        health = self.check_health()

        if health.healthy:
            console.print(f"[green]✓ Healthy (response time: {health.response_time:.2f}s)[/green]")
            return True

        # Health check failed, get logs and analyze
        console.print("[yellow]⚠ Health check failed, analyzing logs...[/yellow]")
        logs = self.get_logs()

        analysis = self.analyze_and_alert(logs, health)

        # Display results
        console.print(f"\n[bold]Analysis Results:[/bold]")
        console.print(f"  Severity: {analysis.get('severity', 'unknown')}")
        console.print(f"  Root Cause: {analysis.get('root_cause', 'unknown')}")

        if analysis.get('suggested_fix'):
            console.print(f"\n[bold green]Suggested Fix:[/bold green]")
            console.print(f"  {analysis['suggested_fix']}")

        return False


class MonitorScheduler:
    """Scheduler for periodic health checks."""

    def __init__(self):
        self.running = False

    def schedule(self, server_name: str, project_name: str, interval_minutes: int = 5):
        """Schedule periodic health checks."""
        import schedule

        def job():
            server = db.get_server(server_name)
            if not server:
                console.print(f"[red]Server {server_name} not found[/red]")
                return

            monitor = Monitor(server, project_name)
            monitor.run_check()

        schedule.every(interval_minutes).minutes.do(job)

        console.print(f"[green]Scheduled health checks every {interval_minutes} minutes[/green]")
        console.print("[dim]Press Ctrl+C to stop[/dim]")

        self.running = True
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(1)
            except KeyboardInterrupt:
                self.running = False
                console.print("\n[yellow]Monitoring stopped[/yellow]")
