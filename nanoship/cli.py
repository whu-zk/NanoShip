"""Command-line interface for NanoShip."""

import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from nanoship.ai_engine import AIEngine
from nanoship.config import settings
from nanoship.database import Server, db
from nanoship.deployer import DeployConfig, Deployer
from nanoship.project_analyzer import ProjectAnalyzer
from nanoship.ssh_manager import SSHManager

app = typer.Typer(
    name="nanoship",
    help="Talk to your server, not the YAML files. AI-powered deployment agent.",
    add_completion=False,
)
console = Console()

# Server management commands
server_app = typer.Typer(help="Manage servers")
app.add_typer(server_app, name="server")

# Deployment commands
deploy_app = typer.Typer(help="Deployment operations")
app.add_typer(deploy_app, name="deploy")


def print_banner():
    """Print the NanoShip banner."""
    banner = """
    ╔═══════════════════════════════════════════╗
    ║                                           ║
    ║   🚀 NanoShip                             ║
    ║   Talk to your server, not the YAML files ║
    ║                                           ║
    ╚═══════════════════════════════════════════╝
    """
    console.print(Panel(banner, style="bold cyan"))


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", "-v", help="Show version"),
):
    """NanoShip - AI-powered deployment agent."""
    if version:
        from nanoship import __version__
        console.print(f"NanoShip version {__version__}")
        raise typer.Exit()


# ═══════════════════════════════════════════════════════════
# Server Commands
# ═══════════════════════════════════════════════════════════

@server_app.command("add")
def server_add(
    name: str = typer.Argument(..., help="Server name (e.g., 'my-vps')"),
    host: str = typer.Argument(..., help="Server IP or hostname"),
    port: int = typer.Option(22, "--port", "-p", help="SSH port"),
    username: str = typer.Option("root", "--user", "-u", help="SSH username"),
    key_path: Optional[str] = typer.Option(None, "--key", "-k", help="Path to SSH private key"),
    password: Optional[str] = typer.Option(None, "--password", help="SSH password (not recommended)"),
):
    """Add a new server to NanoShip."""
    print_banner()

    # Check if server already exists
    if db.get_server(name):
        console.print(f"[red]Error: Server '{name}' already exists. Use 'server update' to modify.[/red]")
        raise typer.Exit(1)

    # Read key content if provided
    key_content = None
    if key_path:
        key_file = Path(key_path).expanduser()
        if key_file.exists():
            key_content = key_file.read_text()
        else:
            console.print(f"[yellow]Warning: Key file not found at {key_path}[/yellow]")

    server = Server(
        name=name,
        host=host,
        port=port,
        username=username,
        password=password,
        key_path=key_path,
        key_content=key_content,
    )

    # Test connection
    console.print(f"[blue]Testing connection to {host}...[/blue]")
    ssh = SSHManager(server)
    if not ssh.connect():
        console.print("[red]Failed to connect to server. Please check your credentials.[/red]")
        raise typer.Exit(1)

    ssh.disconnect()

    # Save to database
    server_id = db.add_server(server)
    console.print(f"[green]✓ Server '{name}' added successfully (ID: {server_id})[/green]")


@server_app.command("list")
def server_list():
    """List all configured servers."""
    servers = db.list_servers()

    if not servers:
        console.print("[yellow]No servers configured. Use 'nanoship server add' to add one.[/yellow]")
        return

    table = Table(title="Configured Servers")
    table.add_column("Name", style="cyan")
    table.add_column("Host", style="green")
    table.add_column("Port", style="yellow")
    table.add_column("User", style="magenta")
    table.add_column("Auth", style="blue")

    for server in servers:
        auth_method = "🔑 Key" if server.key_path or server.key_content else "🔒 Password"
        table.add_row(
            server.name,
            server.host,
            str(server.port),
            server.username,
            auth_method,
        )

    console.print(table)


@server_app.command("remove")
def server_remove(
    name: str = typer.Argument(..., help="Server name to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Remove a server from NanoShip."""
    server = db.get_server(name)
    if not server:
        console.print(f"[red]Error: Server '{name}' not found.[/red]")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(f"Are you sure you want to remove server '{name}'?")
        if not confirm:
            console.print("Cancelled.")
            raise typer.Exit()

    if db.delete_server(name):
        console.print(f"[green]✓ Server '{name}' removed successfully.[/green]")
    else:
        console.print(f"[red]Failed to remove server '{name}'.[/red]")


@server_app.command("test")
def server_test(
    name: str = typer.Argument(..., help="Server name to test"),
):
    """Test SSH connection to a server."""
    server = db.get_server(name)
    if not server:
        console.print(f"[red]Error: Server '{name}' not found.[/red]")
        raise typer.Exit(1)

    console.print(f"[blue]Testing connection to {server.host}...[/blue]")

    ssh = SSHManager(server)
    if ssh.connect():
        # Try to run a simple command
        exit_code, stdout, _ = ssh.execute("uname -a", stream=False)
        if exit_code == 0:
            console.print(f"[green]✓ Connection successful![/green]")
            console.print(f"[dim]Server: {stdout.strip()}[/dim]")
        ssh.disconnect()
    else:
        raise typer.Exit(1)


# ═══════════════════════════════════════════════════════════
# Deploy Commands
# ═══════════════════════════════════════════════════════════

@deploy_app.command("up")
def deploy_up(
    project_path: str = typer.Argument(".", help="Path to project directory"),
    server: str = typer.Argument(..., help="Server name to deploy to"),
    domain: Optional[str] = typer.Option(None, "--domain", "-d", help="Domain name for the app"),
    path: Optional[str] = typer.Option(None, "--path", help="Remote deployment path"),
    no_ssl: bool = typer.Option(False, "--no-ssl", help="Disable automatic SSL"),
):
    """Deploy a project to a remote server."""
    print_banner()

    # Validate project path
    project_path = Path(project_path).resolve()
    if not project_path.exists():
        console.print(f"[red]Error: Project path '{project_path}' does not exist.[/red]")
        raise typer.Exit(1)

    # Get server config
    server_config = db.get_server(server)
    if not server_config:
        console.print(f"[red]Error: Server '{server}' not found. Use 'nanoship server add' first.[/red]")
        raise typer.Exit(1)

    # Connect to server
    ssh = SSHManager(server_config)
    if not ssh.connect():
        raise typer.Exit(1)

    try:
        # Create deployer and execute deployment
        deployer = Deployer(ssh)
        config = DeployConfig(
            project_path=str(project_path),
            server_name=server,
            remote_path=path,
            domain=domain,
            ssl=not no_ssl,
        )

        success = deployer.deploy(config)

        if success:
            # Record deployment
            from nanoship.database import Deployment
            deployment = Deployment(
                server_id=server_config.id,
                project_name=project_path.name,
                project_path=str(project_path),
                remote_path=path or f"{settings.default_deploy_path}/{project_path.name}",
                domain=domain,
                status="success",
            )
            db.add_deployment(deployment)

    finally:
        ssh.disconnect()


@deploy_app.command("logs")
def deploy_logs(
    server: str = typer.Argument(..., help="Server name"),
    project: str = typer.Argument(..., help="Project name"),
    tail: int = typer.Option(50, "--tail", "-n", help="Number of lines to show"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
):
    """View deployment logs."""
    server_config = db.get_server(server)
    if not server_config:
        console.print(f"[red]Error: Server '{server}' not found.[/red]")
        raise typer.Exit(1)

    ssh = SSHManager(server_config)
    if not ssh.connect():
        raise typer.Exit(1)

    try:
        remote_path = f"{settings.default_deploy_path}/{project}"

        if follow:
            console.print("[dim]Press Ctrl+C to exit[/dim]")
            ssh.execute(f"cd {remote_path} && docker-compose logs -f --tail={tail}")
        else:
            exit_code, stdout, _ = ssh.execute(
                f"cd {remote_path} && docker-compose logs --tail={tail}",
                stream=False
            )
            console.print(stdout)
    finally:
        ssh.disconnect()


@deploy_app.command("status")
def deploy_status(
    server: Optional[str] = typer.Option(None, "--server", "-s", help="Filter by server"),
):
    """Show deployment status."""
    deployments = db.list_deployments()

    if not deployments:
        console.print("[yellow]No deployments found.[/yellow]")
        return

    table = Table(title="Deployment History")
    table.add_column("ID", style="dim")
    table.add_column("Project", style="cyan")
    table.add_column("Server", style="green")
    table.add_column("Domain", style="magenta")
    table.add_column("Status", style="yellow")
    table.add_column("Created", style="blue")

    for dep in deployments:
        server_name = db.get_server_by_id(dep.server_id)
        server_name = server_name.name if server_name else "Unknown"

        status_color = {
            "success": "green",
            "failed": "red",
            "pending": "yellow",
            "rolled_back": "orange",
        }.get(dep.status, "white")

        table.add_row(
            str(dep.id),
            dep.project_name,
            server_name,
            dep.domain or "-",
            f"[{status_color}]{dep.status}[/{status_color}]",
            dep.created_at or "-",
        )

    console.print(table)


# ═══════════════════════════════════════════════════════════
# Main Commands
# ═══════════════════════════════════════════════════════════

@app.command()
def analyze(
    path: str = typer.Argument(".", help="Path to project directory"),
    generate: bool = typer.Option(False, "--generate", "-g", help="Generate Docker files"),
):
    """Analyze a project and show deployment recommendations."""
    print_banner()

    project_path = Path(path).resolve()
    if not project_path.exists():
        console.print(f"[red]Error: Path '{path}' does not exist.[/red]")
        raise typer.Exit(1)

    analyzer = ProjectAnalyzer(str(project_path))
    info = analyzer.analyze()

    if generate:
        analyzer.write_docker_files(info)

    # AI analysis
    console.print("[blue]Getting AI recommendations...[/blue]")
    ai = AIEngine()
    recommendations = ai.analyze_project({
        "name": info.name,
        "language": info.language,
        "framework": info.framework,
        "port": info.port,
        "dependencies": info.dependencies,
    })

    if recommendations.get("recommendations"):
        console.print("\n[bold green]💡 AI Recommendations:[/bold green]")
        for rec in recommendations["recommendations"]:
            console.print(f"  • {rec}")

    if recommendations.get("security_concerns"):
        console.print("\n[bold yellow]⚠️  Security Concerns:[/bold yellow]")
        for concern in recommendations["security_concerns"]:
            console.print(f"  • {concern}")


@app.command()
def audit(
    server: str = typer.Argument(..., help="Server name to audit"),
):
    """Run security audit on a server."""
    print_banner()

    server_config = db.get_server(server)
    if not server_config:
        console.print(f"[red]Error: Server '{server}' not found.[/red]")
        raise typer.Exit(1)

    console.print(f"[blue]Running security audit on {server}...[/blue]\n")

    ssh = SSHManager(server_config)
    if not ssh.connect():
        raise typer.Exit(1)

    try:
        # Collect server information
        checks = {
            "OS Version": "cat /etc/os-release | head -5",
            "Disk Usage": "df -h | grep -E '^/dev'",
            "Memory Usage": "free -h",
            "Running Containers": "docker ps --format 'table {{.Names}}\\t{{.Status}}' 2>/dev/null || echo 'Docker not installed'",
            "Open Ports": "ss -tuln | grep LISTEN",
            "Failed Logins": "grep 'Failed password' /var/log/auth.log 2>/dev/null | tail -5 || echo 'No recent failures'",
        }

        results = {}
        for name, command in checks.items():
            exit_code, stdout, _ = ssh.execute(command, stream=False)
            results[name] = stdout.strip()

        # Display results
        for name, output in results.items():
            console.print(Panel(output, title=name, border_style="blue"))

        # AI audit
        console.print("[blue]Getting AI security analysis...[/blue]")
        ai = AIEngine()
        audit_result = ai.audit_server(results)

        score = audit_result.get("security_score", 50)
        score_color = "green" if score >= 80 else "yellow" if score >= 60 else "red"

        console.print(f"\n[bold]Security Score: [{score_color}]{score}/100[/{score_color}][/bold]")

        if audit_result.get("critical_issues"):
            console.print("\n[bold red]🔴 Critical Issues:[/bold red]")
            for issue in audit_result["critical_issues"]:
                console.print(f"  • {issue}")

        if audit_result.get("recommendations"):
            console.print("\n[bold green]💡 Recommendations:[/bold green]")
            for rec in audit_result["recommendations"]:
                console.print(f"  • {rec}")

    finally:
        ssh.disconnect()


@app.command()
def doctor(
    fix: bool = typer.Option(False, "--fix", help="Attempt to fix issues automatically"),
):
    """Check NanoShip configuration and dependencies."""
    print_banner()

    console.print("[bold]Running diagnostics...[/bold]\n")

    checks = []

    # Check Python version
    import sys
    py_version = sys.version_info
    checks.append((
        "Python Version",
        f"{py_version.major}.{py_version.minor}.{py_version.micro}",
        py_version >= (3, 10),
    ))

    # Check Docker
    import subprocess
    try:
        result = subprocess.run(["docker", "--version"], capture_output=True, text=True)
        docker_ok = result.returncode == 0
        checks.append(("Docker", result.stdout.strip() if docker_ok else "Not found", docker_ok))
    except FileNotFoundError:
        checks.append(("Docker", "Not installed", False))

    # Check SSH key
    ssh_key_path = Path("~/.ssh/id_rsa").expanduser()
    checks.append(("SSH Key", str(ssh_key_path), ssh_key_path.exists()))

    # Check API key
    api_key_set = settings.llm_api_key is not None
    checks.append(("LLM API Key", "Configured" if api_key_set else "Not set", api_key_set))

    # Display results
    table = Table(title="System Check")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("OK", style="yellow")

    for name, status, ok in checks:
        status_str = "[green]✓[/green]" if ok else "[red]✗[/red]"
        table.add_row(name, status, status_str)

    console.print(table)

    # Summary
    all_ok = all(ok for _, _, ok in checks)
    if all_ok:
        console.print("\n[bold green]✓ All systems ready![/bold green]")
    else:
        console.print("\n[bold yellow]⚠ Some checks failed. See above for details.[/bold yellow]")


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
