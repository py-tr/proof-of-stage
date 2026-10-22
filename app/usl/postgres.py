"""Postgres DDL for the append-only audit tables, via the oa-pg container."""

from __future__ import annotations

import re
import subprocess

from app.usl.errors import SetupError, public_error
from app.usl.model import PG_CONTAINER, PG_DATABASE

_USER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_SECRET_MARKERS = ("PASSWORD", "SECRET", "TOKEN", "KEY")


def discover_user() -> tuple[str, list[str]]:
    """Read POSTGRES_USER from the container. The password is returned only for scrubbing."""
    completed = subprocess.run(
        ["docker", "exec", PG_CONTAINER, "env"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        detail = public_error(completed.stderr or "could not read the database container")
        raise SetupError(detail or "could not read the database container")
    return user_from_env(completed.stdout)


def user_from_env(env_text: str) -> tuple[str, list[str]]:
    values: dict[str, str] = {}
    for line in env_text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    user = values.get("POSTGRES_USER") or values.get("PGUSER")
    secrets = [
        value
        for key, value in values.items()
        if value and any(marker in key.upper() for marker in _SECRET_MARKERS)
    ]
    if not user or not _USER_RE.fullmatch(user):
        raise SetupError("Postgres user is unset on the database container")
    return user, secrets


def apply_ddl(user: str, sql: str, secrets: list[str] | None = None) -> None:
    """Run DDL inside oa-pg. Every column is declared here because inserts pass all columns."""
    if not _USER_RE.fullmatch(user):
        raise SetupError("Postgres user is not a plain identifier")
    completed = subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            PG_CONTAINER,
            "psql",
            "-U",
            user,
            "-d",
            PG_DATABASE,
            "-v",
            "ON_ERROR_STOP=1",
            "-q",
        ],
        input=sql,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        detail = public_error(completed.stderr or "postgres command failed", secrets)
        raise SetupError(detail or "postgres command failed")
