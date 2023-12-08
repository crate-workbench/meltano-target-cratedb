"""Postgres target class."""
from __future__ import annotations

from target_postgres.target import TargetPostgres

from target_cratedb.sinks import CrateDBSink


class TargetCrateDB(TargetPostgres):
    """Target for CrateDB."""

    name = "target-cratedb"

    default_sink_class = CrateDBSink
