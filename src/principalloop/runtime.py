"""Local runtime admission and qualification.

Admission protects the kernel: CPython 3.13.x with a SQLite that carries the WAL fix.
Qualification also requires the reference runtime used for the published evidence.
The probes prove neither crash recovery nor power-loss durability.
"""

from __future__ import annotations

from importlib.metadata import version
from pathlib import Path
import platform
import sqlite3
import sys
import tempfile


REFERENCE_PYTHON = (3, 13, 16)
SUPPORTED_SERIES = (3, 13)


def sqlite_has_wal_reset_fix(release: tuple[int, int, int]) -> bool:
    """Explicit S5 policy; no global comparison against the smallest backport."""
    return (
        release >= (3, 51, 3)
        or release[:2] == (3, 50) and release[2] >= 7
        or release[:2] == (3, 44) and release[2] >= 6
    )


def runtime_admitted(version_info=None, sqlite_release=None) -> bool:
    """Conditions bloquantes du noyau ; la version corrective exacte reste informative."""
    version_info = sys.version_info if version_info is None else version_info
    sqlite_release = sqlite3.sqlite_version_info if sqlite_release is None else sqlite_release
    return tuple(version_info[:2]) == SUPPORTED_SERIES and sqlite_has_wal_reset_fix(tuple(sqlite_release))


def probe_sqlite() -> tuple[dict[str, bool], str]:
    checks: dict[str, bool] = {}
    with tempfile.TemporaryDirectory(prefix="principalloop-doctor-") as folder:
        target = Path(folder).resolve()
        # Automatic deletion stays limited to the temporary directory created here.
        assert target.is_relative_to(Path(tempfile.gettempdir()).resolve())
        database = target / "probe.sqlite3"
        connection = sqlite3.connect(database, autocommit=True, timeout=1)
        try:
            source_id = connection.execute("SELECT sqlite_source_id()").fetchone()[0]
            checks["wal"] = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA synchronous=FULL")
            checks["foreign_keys_enabled"] = connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
            checks["synchronous_full"] = connection.execute("PRAGMA synchronous").fetchone()[0] == 2
            connection.execute("CREATE TABLE parent(id INTEGER PRIMARY KEY)")
            connection.execute("CREATE TABLE child(parent_id INTEGER REFERENCES parent(id))")
            connection.execute("BEGIN")
            connection.execute("INSERT INTO parent VALUES (1)")
            connection.execute("COMMIT")
            connection.execute("BEGIN")
            connection.execute("INSERT INTO parent VALUES (2)")
            connection.execute("ROLLBACK")
            checks["rollback"] = connection.execute("SELECT id FROM parent").fetchall() == [(1,)]
            try:
                connection.execute("INSERT INTO child VALUES (999)")
            except sqlite3.IntegrityError:
                checks["foreign_key_rejection"] = True
            else:
                checks["foreign_key_rejection"] = False
            checks["integrity"] = connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        finally:
            connection.close()
        connection = sqlite3.connect(database, autocommit=True, timeout=1)
        try:
            checks["committed_data_after_reopen"] = connection.execute("SELECT id FROM parent").fetchall() == [(1,)]
            checks["wal_after_reopen"] = connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        finally:
            connection.close()
    return checks, source_id


def diagnose() -> dict:
    checks = {
        "cpython": platform.python_implementation() == "CPython",
        "python_series": sys.version_info[:2] == SUPPORTED_SERIES,
        "sqlite_wal_reset_fix": sqlite_has_wal_reset_fix(sqlite3.sqlite_version_info),
    }
    report = {
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_build": sys.version,
        "sqlite": sqlite3.sqlite_version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "packages": {name: version(name) for name in ("principalloop", "jsonschema", "referencing", "rfc3339-validator")},
        "checks": checks,
        "limits": ["No crash recovery test", "No power loss test", "No performance claim", "No runner qualification"],
    }
    if all(checks.values()):
        try:
            probes, source_id = probe_sqlite()
            checks.update(probes)
            report["sqlite_source_id"] = source_id
        except (sqlite3.Error, OSError) as error:
            checks["sqlite_probe"] = False
            report["probe_error"] = str(error)
    report["admitted"] = all(checks.values())
    report["reference_runtime"] = sys.version_info[:3] == REFERENCE_PYTHON
    report["reference_python"] = ".".join(map(str, REFERENCE_PYTHON))
    # Qualified = admitted + the exact runtime used for the published evidence.
    report["qualified"] = report["admitted"] and report["reference_runtime"]
    return report
