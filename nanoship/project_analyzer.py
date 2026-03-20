"""Project analysis and Dockerfile generation using AI."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import toml
import yaml
from jinja2 import Template
from rich.console import Console

from nanoship.config import settings

console = Console()


@dataclass
class ProjectInfo:
    """Information about a project."""

    name: str
    language: str
    framework: Optional[str]
    port: int
    build_command: Optional[str]
    start_command: str
    env_vars: list[str]
    dependencies: list[str]
    has_dockerfile: bool
    has_docker_compose: bool
    project_type: str  # web, api, worker, static


# Dockerfile templates for different languages
DOCKERFILE_TEMPLATES = {
    "python": """FROM python:{{ python_version }}-slim

WORKDIR /app

{% if has_requirements %}
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
{% elif has_pyproject %}
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .
{% endif %}

COPY . .

EXPOSE {{ port }}

{% if start_command %}
CMD {{ start_command }}
{% else %}
CMD ["python", "-m", "{{ module_name }}"]
{% endif %}
""",
    "node": """FROM node:{{ node_version }}-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

COPY . .

{% if build_command %}
RUN {{ build_command }}
{% endif %}

EXPOSE {{ port }}

{% if start_command %}
CMD {{ start_command }}
{% else %}
CMD ["node", "{{ entry_point }}"]
{% endif %}
""",
    "go": """FROM golang:{{ go_version }}-alpine AS builder

WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o app {{ main_file }}

FROM alpine:latest
RUN apk --no-cache add ca-certificates

WORKDIR /root/

COPY --from=builder /app/app .

EXPOSE {{ port }}

CMD ["./app"]
""",
    "rust": """FROM rust:{{ rust_version }}-slim AS builder

WORKDIR /app

COPY Cargo.toml Cargo.lock ./
RUN mkdir src && echo "fn main() {}" > src/main.rs
RUN cargo build --release && rm -rf src

COPY . .
RUN cargo build --release

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/target/release/{{ binary_name }} ./app

EXPOSE {{ port }}

CMD ["./app"]
""",
    "static": """FROM nginx:alpine

COPY . /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
""",
}

# docker-compose.yml template
DOCKER_COMPOSE_TEMPLATE = """version: '3.8'

services:
  {{ service_name }}:
    build: .
    container_name: {{ service_name }}
    restart: unless-stopped
    ports:
      - "{{ host_port }}:{{ container_port }}"
    {% if env_vars %}
    environment:
      {% for env in env_vars %}
      - {{ env }}
      {% endfor %}
    {% endif %}
    {% if volumes %}
    volumes:
      {% for vol in volumes %}
      - {{ vol }}
      {% endfor %}
    {% endif %}
    {% if networks %}
    networks:
      {% for net in networks %}
      - {{ net }}
      {% endfor %}
    {% endif %}

{% if networks %}
networks:
  {% for net in networks %}
  {{ net }}:
    driver: bridge
  {% endfor %}
{% endif %}
"""


class ProjectAnalyzer:
    """Analyzes project structure and generates deployment configurations."""

    def __init__(self, project_path: str):
        self.project_path = Path(project_path).resolve()
        self.project_name = self.project_path.name

    def analyze(self) -> ProjectInfo:
        """Analyze the project and return project information."""
        console.print(f"[blue]Analyzing project: {self.project_name}[/blue]")

        # Detect language and framework
        language, framework = self._detect_language()
        port = self._detect_port(language, framework)
        build_cmd, start_cmd = self._detect_commands(language, framework)
        env_vars = self._detect_env_vars()
        deps = self._detect_dependencies(language)

        # Check for existing Docker files
        has_dockerfile = (self.project_path / "Dockerfile").exists()
        has_compose = (self.project_path / "docker-compose.yml").exists() or (
            self.project_path / "docker-compose.yaml"
        ).exists()

        # Determine project type
        project_type = self._detect_project_type(language, framework)

        info = ProjectInfo(
            name=self.project_name,
            language=language,
            framework=framework,
            port=port,
            build_command=build_cmd,
            start_command=start_cmd,
            env_vars=env_vars,
            dependencies=deps,
            has_dockerfile=has_dockerfile,
            has_docker_compose=has_compose,
            project_type=project_type,
        )

        self._print_analysis(info)
        return info

    def _detect_language(self) -> tuple[str, Optional[str]]:
        """Detect the programming language and framework."""
        files = list(self.project_path.iterdir())
        file_names = {f.name for f in files}

        # Python
        if any(f in file_names for f in ["requirements.txt", "pyproject.toml", "setup.py", "Pipfile"]):
            framework = None
            if "fastapi" in self._read_requirements():
                framework = "fastapi"
            elif "flask" in self._read_requirements():
                framework = "flask"
            elif "django" in self._read_requirements():
                framework = "django"
            return "python", framework

        # Node.js
        if "package.json" in file_names:
            pkg = self._read_package_json()
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

            framework = None
            if "next" in deps:
                framework = "nextjs"
            elif "react" in deps:
                framework = "react"
            elif "vue" in deps:
                framework = "vue"
            elif "express" in deps:
                framework = "express"
            elif "@nestjs/core" in deps:
                framework = "nestjs"

            return "node", framework

        # Go
        if "go.mod" in file_names:
            return "go", None

        # Rust
        if "Cargo.toml" in file_names:
            return "rust", None

        # Static site (HTML/CSS/JS)
        if any(f.suffix in [".html", ".css", ".js"] for f in files if f.is_file()):
            return "static", None

        return "unknown", None

    def _detect_port(self, language: str, framework: Optional[str]) -> int:
        """Detect the default port for the project."""
        # Check for PORT in .env or config files
        env_file = self.project_path / ".env"
        if env_file.exists():
            content = env_file.read_text()
            for line in content.split("\n"):
                if line.startswith("PORT="):
                    try:
                        return int(line.split("=")[1].strip())
                    except ValueError:
                        pass

        # Default ports by framework
        port_map = {
            "fastapi": 8000,
            "flask": 5000,
            "django": 8000,
            "react": 3000,
            "vue": 8080,
            "nextjs": 3000,
            "express": 3000,
            "nestjs": 3000,
        }

        if framework and framework in port_map:
            return port_map[framework]

        # Default by language
        lang_ports = {"python": 8000, "node": 3000, "go": 8080, "rust": 8080, "static": 80}
        return lang_ports.get(language, 8080)

    def _detect_commands(self, language: str, framework: Optional[str]) -> tuple[Optional[str], str]:
        """Detect build and start commands."""
        if language == "node":
            pkg = self._read_package_json()
            scripts = pkg.get("scripts", {})

            build_cmd = scripts.get("build")
            start_cmd = scripts.get("start", "node index.js")

            # Adjust for different frameworks
            if framework == "nextjs":
                build_cmd = build_cmd or "npm run build"
                start_cmd = start_cmd or "npm start"

            return build_cmd, start_cmd

        elif language == "python":
            if framework == "fastapi":
                return None, "uvicorn main:app --host 0.0.0.0 --port 8000"
            elif framework == "flask":
                return None, "flask run --host=0.0.0.0"
            elif framework == "django":
                return None, "python manage.py runserver 0.0.0.0:8000"
            else:
                return None, "python main.py"

        elif language == "go":
            return "go build -o app", "./app"

        elif language == "rust":
            return "cargo build --release", "./target/release/app"

        elif language == "static":
            return None, "nginx -g 'daemon off;'"

        return None, "echo 'No start command detected'"

    def _detect_env_vars(self) -> list[str]:
        """Detect environment variables from .env.example or .env."""
        env_vars = []

        for env_file in [".env.example", ".env"]:
            path = self.project_path / env_file
            if path.exists():
                content = path.read_text()
                for line in content.split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        env_vars.append(line)

        return env_vars

    def _detect_dependencies(self, language: str) -> list[str]:
        """Detect project dependencies."""
        deps = []

        if language == "python":
            req_file = self.project_path / "requirements.txt"
            if req_file.exists():
                deps = [line.strip() for line in req_file.read_text().split("\n") if line.strip()]

        elif language == "node":
            pkg = self._read_package_json()
            deps = list(pkg.get("dependencies", {}).keys())

        return deps

    def _detect_project_type(self, language: str, framework: Optional[str]) -> str:
        """Detect the type of project."""
        if language == "static":
            return "static"
        if framework in ["fastapi", "express", "nestjs", "flask", "django"]:
            return "api"
        if framework in ["react", "vue", "nextjs"]:
            return "web"
        return "api"

    def _read_requirements(self) -> str:
        """Read requirements.txt content."""
        req_file = self.project_path / "requirements.txt"
        if req_file.exists():
            return req_file.read_text().lower()
        return ""

    def _read_package_json(self) -> dict:
        """Read package.json content."""
        pkg_file = self.project_path / "package.json"
        if pkg_file.exists():
            return json.loads(pkg_file.read_text())
        return {}

    def _print_analysis(self, info: ProjectInfo):
        """Print project analysis results."""
        console.print("\n[bold green]📋 Project Analysis Results:[/bold green]")
        console.print(f"  [cyan]Name:[/cyan] {info.name}")
        console.print(f"  [cyan]Language:[/cyan] {info.language}")
        if info.framework:
            console.print(f"  [cyan]Framework:[/cyan] {info.framework}")
        console.print(f"  [cyan]Type:[/cyan] {info.project_type}")
        console.print(f"  [cyan]Port:[/cyan] {info.port}")
        if info.build_command:
            console.print(f"  [cyan]Build:[/cyan] {info.build_command}")
        console.print(f"  [cyan]Start:[/cyan] {info.start_command}")
        if info.env_vars:
            console.print(f"  [cyan]Env Vars:[/cyan] {len(info.env_vars)} found")
        console.print()

    def generate_dockerfile(self, info: ProjectInfo) -> str:
        """Generate a Dockerfile for the project."""
        if info.language not in DOCKERFILE_TEMPLATES:
            console.print(f"[yellow]Warning: No template for {info.language}, using generic[/yellow]")
            return self._generate_generic_dockerfile(info)

        template = Template(DOCKERFILE_TEMPLATES[info.language])

        context = {
            "port": info.port,
            "start_command": json.dumps(info.start_command.split()) if " " in info.start_command else f'["{info.start_command}"]',
        }

        # Language-specific context
        if info.language == "python":
            context.update({
                "python_version": "3.11",
                "has_requirements": (self.project_path / "requirements.txt").exists(),
                "has_pyproject": (self.project_path / "pyproject.toml").exists(),
                "module_name": info.name.replace("-", "_").lower(),
            })

        elif info.language == "node":
            pkg = self._read_package_json()
            context.update({
                "node_version": "20",
                "build_command": info.build_command,
                "entry_point": pkg.get("main", "index.js"),
            })

        elif info.language == "go":
            go_files = list(self.project_path.glob("*.go"))
            main_file = "main.go"
            if go_files:
                for f in go_files:
                    content = f.read_text()
                    if "func main()" in content:
                        main_file = f.name
                        break
            context.update({
                "go_version": "1.21",
                "main_file": main_file,
            })

        elif info.language == "rust":
            cargo = toml.load(self.project_path / "Cargo.toml")
            context.update({
                "rust_version": "1.75",
                "binary_name": cargo.get("package", {}).get("name", "app"),
            })

        return template.render(**context)

    def generate_docker_compose(self, info: ProjectInfo) -> str:
        """Generate a docker-compose.yml for the project."""
        template = Template(DOCKER_COMPOSE_TEMPLATE)

        context = {
            "service_name": info.name.lower().replace(" ", "-"),
            "host_port": info.port,
            "container_port": info.port,
            "env_vars": info.env_vars,
            "volumes": [],
            "networks": ["nanoship"] if info.project_type == "api" else [],
        }

        return template.render(**context)

    def _generate_generic_dockerfile(self, info: ProjectInfo) -> str:
        """Generate a generic Dockerfile when no specific template exists."""
        return f"""# Generic Dockerfile for {info.language}
FROM alpine:latest

WORKDIR /app

COPY . .

EXPOSE {info.port}

CMD {info.start_command}
"""

    def write_docker_files(self, info: ProjectInfo, output_dir: Optional[str] = None) -> tuple[str, str]:
        """Generate and write Docker files to the project directory."""
        output_path = Path(output_dir) if output_dir else self.project_path

        # Generate Dockerfile
        dockerfile_content = self.generate_dockerfile(info)
        dockerfile_path = output_path / "Dockerfile"
        dockerfile_path.write_text(dockerfile_content)
        console.print(f"[green]✓ Generated {dockerfile_path}[/green]")

        # Generate docker-compose.yml
        compose_content = self.generate_docker_compose(info)
        compose_path = output_path / "docker-compose.yml"
        compose_path.write_text(compose_content)
        console.print(f"[green]✓ Generated {compose_path}[/green]")

        return str(dockerfile_path), str(compose_path)
