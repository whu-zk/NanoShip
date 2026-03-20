"""SQLite database management for NanoShip."""

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from nanoship.config import settings


@dataclass
class Server:
    """Server configuration model."""

    id: Optional[int] = None
    name: str = ""
    host: str = ""
    port: int = 22
    username: str = "root"
    password: Optional[str] = None
    key_path: Optional[str] = None
    key_content: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class Deployment:
    """Deployment record model."""

    id: Optional[int] = None
    server_id: int = 0
    project_name: str = ""
    project_path: str = ""
    remote_path: str = ""
    domain: Optional[str] = None
    status: str = "pending"  # pending, success, failed, rolled_back
    logs: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


class Database:
    """SQLite database manager."""

    def __init__(self):
        self.db_path = settings.db_full_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize database tables."""
        with self._get_connection() as conn:
            # Servers table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS servers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    host TEXT NOT NULL,
                    port INTEGER DEFAULT 22,
                    username TEXT DEFAULT 'root',
                    password TEXT,
                    key_path TEXT,
                    key_content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Deployments table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS deployments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    server_id INTEGER NOT NULL,
                    project_name TEXT NOT NULL,
                    project_path TEXT NOT NULL,
                    remote_path TEXT NOT NULL,
                    domain TEXT,
                    status TEXT DEFAULT 'pending',
                    logs TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    FOREIGN KEY (server_id) REFERENCES servers (id)
                )
            """)

            conn.commit()

    # Server operations
    def add_server(self, server: Server) -> int:
        """Add a new server."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO servers (name, host, port, username, password, key_path, key_content)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    server.name,
                    server.host,
                    server.port,
                    server.username,
                    server.password,
                    server.key_path,
                    server.key_content,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_server(self, name: str) -> Optional[Server]:
        """Get server by name."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM servers WHERE name = ?",
                (name,)
            ).fetchone()

            if row:
                return Server(**dict(row))
            return None

    def get_server_by_id(self, server_id: int) -> Optional[Server]:
        """Get server by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM servers WHERE id = ?",
                (server_id,)
            ).fetchone()

            if row:
                return Server(**dict(row))
            return None

    def list_servers(self) -> list[Server]:
        """List all servers."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM servers ORDER BY created_at DESC"
            ).fetchall()
            return [Server(**dict(row)) for row in rows]

    def update_server(self, server: Server) -> bool:
        """Update server information."""
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE servers
                SET host = ?, port = ?, username = ?, password = ?, key_path = ?, key_content = ?, updated_at = CURRENT_TIMESTAMP
                WHERE name = ?
                """,
                (
                    server.host,
                    server.port,
                    server.username,
                    server.password,
                    server.key_path,
                    server.key_content,
                    server.name,
                ),
            )
            conn.commit()
            return conn.total_changes > 0

    def delete_server(self, name: str) -> bool:
        """Delete a server."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM servers WHERE name = ?", (name,))
            conn.commit()
            return conn.total_changes > 0

    # Deployment operations
    def add_deployment(self, deployment: Deployment) -> int:
        """Add a new deployment record."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO deployments (server_id, project_name, project_path, remote_path, domain, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    deployment.server_id,
                    deployment.project_name,
                    deployment.project_path,
                    deployment.remote_path,
                    deployment.domain,
                    deployment.status,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def update_deployment_status(
        self, deployment_id: int, status: str, logs: Optional[str] = None
    ) -> bool:
        """Update deployment status."""
        with self._get_connection() as conn:
            if status in ["success", "failed", "rolled_back"]:
                conn.execute(
                    """
                    UPDATE deployments
                    SET status = ?, logs = ?, completed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (status, logs, deployment_id),
                )
            else:
                conn.execute(
                    "UPDATE deployments SET status = ?, logs = ? WHERE id = ?",
                    (status, logs, deployment_id),
                )
            conn.commit()
            return conn.total_changes > 0

    def get_deployment(self, deployment_id: int) -> Optional[Deployment]:
        """Get deployment by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM deployments WHERE id = ?",
                (deployment_id,)
            ).fetchone()

            if row:
                return Deployment(**dict(row))
            return None

    def list_deployments(self, server_id: Optional[int] = None) -> list[Deployment]:
        """List deployments, optionally filtered by server."""
        with self._get_connection() as conn:
            if server_id:
                rows = conn.execute(
                    "SELECT * FROM deployments WHERE server_id = ? ORDER BY created_at DESC",
                    (server_id,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM deployments ORDER BY created_at DESC"
                ).fetchall()
            return [Deployment(**dict(row)) for row in rows]

    def get_latest_deployment(self, project_name: str) -> Optional[Deployment]:
        """Get the latest deployment for a project."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM deployments WHERE project_name = ? ORDER BY created_at DESC LIMIT 1",
                (project_name,)
            ).fetchone()

            if row:
                return Deployment(**dict(row))
            return None


# Global database instance
db = Database()
