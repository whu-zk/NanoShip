"""Tests for project analyzer."""

import tempfile
from pathlib import Path

import pytest

from nanoship.project_analyzer import ProjectAnalyzer, ProjectInfo


class TestProjectAnalyzer:
    """Test cases for ProjectAnalyzer."""

    def test_detect_python_fastapi(self):
        """Test detection of FastAPI project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create requirements.txt with FastAPI
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text("fastapi\nuvicorn\npydantic\n")

            analyzer = ProjectAnalyzer(tmpdir)
            info = analyzer.analyze()

            assert info.language == "python"
            assert info.framework == "fastapi"
            assert info.port == 8000

    def test_detect_python_flask(self):
        """Test detection of Flask project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text("flask\nrequests\n")

            analyzer = ProjectAnalyzer(tmpdir)
            info = analyzer.analyze()

            assert info.language == "python"
            assert info.framework == "flask"
            assert info.port == 5000

    def test_detect_node_express(self):
        """Test detection of Express.js project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_file = Path(tmpdir) / "package.json"
            pkg_file.write_text('{"dependencies": {"express": "^4.18.0"}}')

            analyzer = ProjectAnalyzer(tmpdir)
            info = analyzer.analyze()

            assert info.language == "node"
            assert info.framework == "express"

    def test_detect_node_nextjs(self):
        """Test detection of Next.js project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_file = Path(tmpdir) / "package.json"
            pkg_file.write_text('{"dependencies": {"next": "^14.0.0", "react": "^18.0.0"}}')

            analyzer = ProjectAnalyzer(tmpdir)
            info = analyzer.analyze()

            assert info.language == "node"
            assert info.framework == "nextjs"

    def test_detect_go(self):
        """Test detection of Go project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            go_mod = Path(tmpdir) / "go.mod"
            go_mod.write_text("module example.com/app\ngo 1.21\n")

            analyzer = ProjectAnalyzer(tmpdir)
            info = analyzer.analyze()

            assert info.language == "go"

    def test_detect_rust(self):
        """Test detection of Rust project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cargo_toml = Path(tmpdir) / "Cargo.toml"
            cargo_toml.write_text('[package]\nname = "myapp"\nversion = "0.1.0"\n')

            analyzer = ProjectAnalyzer(tmpdir)
            info = analyzer.analyze()

            assert info.language == "rust"

    def test_generate_dockerfile_python(self):
        """Test Dockerfile generation for Python project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text("fastapi\nuvicorn\n")

            analyzer = ProjectAnalyzer(tmpdir)
            info = analyzer.analyze()
            dockerfile = analyzer.generate_dockerfile(info)

            assert "FROM python:" in dockerfile
            assert "requirements.txt" in dockerfile
            assert str(info.port) in dockerfile

    def test_generate_dockerfile_node(self):
        """Test Dockerfile generation for Node.js project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_file = Path(tmpdir) / "package.json"
            pkg_file.write_text('{"dependencies": {"express": "^4.18.0"}}')

            analyzer = ProjectAnalyzer(tmpdir)
            info = analyzer.analyze()
            dockerfile = analyzer.generate_dockerfile(info)

            assert "FROM node:" in dockerfile
            assert "npm" in dockerfile

    def test_generate_docker_compose(self):
        """Test docker-compose.yml generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text("fastapi\n")

            analyzer = ProjectAnalyzer(tmpdir)
            info = analyzer.analyze()
            compose = analyzer.generate_docker_compose(info)

            assert "version:" in compose or "services:" in compose
            assert info.name.lower() in compose
            assert str(info.port) in compose


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
