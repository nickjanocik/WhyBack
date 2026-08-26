"""Central DuckDB boundary for all deterministic analytical queries."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from whyback.config import SOURCE_COMMIT, SOURCE_REPOSITORY
from whyback.data.download import SOURCE_FILES, sha256_file
from whyback.data.manifest import (
    PREPARATION_TRANSFORM_VERSION,
    DataManifest,
    preparation_code_sha256,
    read_manifest,
)


class PreparedDataError(RuntimeError):
    """Prepared tables are absent, corrupt, or incompatible."""


TABLE_FILES: Mapping[str, str] = {
    "transactions": "transactions.parquet",
    "products": "products.parquet",
    "demographics": "demographics.parquet",
    "campaigns": "campaigns.parquet",
    "campaign_descriptions": "campaign_descriptions.parquet",
    "coupons": "coupons.parquet",
    "coupon_redemptions": "coupon_redemptions.parquet",
    "promotion_state": "promotion_state.parquet",
    "household_week": "household_week.parquet",
    "baskets": "baskets.parquet",
}


def _quote_path(path: Path) -> str:
    """Resolve a path and escape apostrophes for a DuckDB SQL string literal."""

    return str(path.resolve()).replace("'", "''")


class DataRepository:
    """Own a DuckDB connection and registered read-only Parquet views."""

    def __init__(
        self,
        prepared_dir: Path,
        *,
        required_tables: Iterable[str] = TABLE_FILES,
        validate_manifest: bool = True,
    ) -> None:
        """Validate prepared inputs and expose the requested Parquet files as views."""

        self.prepared_dir = prepared_dir
        tables = tuple(required_tables)
        self._required_tables = tables
        unknown = set(tables).difference(TABLE_FILES)
        if unknown:
            raise PreparedDataError(f"Unknown prepared tables: {sorted(unknown)}")
        for table in tables:
            path = prepared_dir / TABLE_FILES[table]
            if not path.is_file():
                raise PreparedDataError(f"Prepared table is missing: {path}")
        self.manifest = self._validated_manifest(tables) if validate_manifest else None
        self._connection = duckdb.connect()
        self._connection.execute("SET TimeZone = 'America/New_York'")
        try:
            for table in tables:
                path = prepared_dir / TABLE_FILES[table]
                self._connection.execute(
                    f"CREATE VIEW {table} AS SELECT * FROM "
                    f"read_parquet('{_quote_path(path)}')"
                )
        except Exception:
            self._connection.close()
            raise

    def _validated_manifest(self, tables: tuple[str, ...]) -> DataManifest:
        """Verify identity, transform version, declarations, and table hashes."""

        manifest_path = self.prepared_dir / "manifest.json"
        if not manifest_path.is_file():
            raise PreparedDataError(
                f"Prepared data manifest is missing: {manifest_path}"
            )
        try:
            manifest = read_manifest(manifest_path)
        except (OSError, ValueError) as error:
            raise PreparedDataError(
                f"Prepared data manifest is invalid: {error}"
            ) from error
        if (
            manifest.preparation_transform_version != PREPARATION_TRANSFORM_VERSION
            or manifest.preparation_code_sha256 != preparation_code_sha256()
        ):
            raise PreparedDataError(
                "Prepared data was produced by a stale preparation transform; "
                "run data preparation again."
            )
        source_entries = {entry.filename: entry for entry in manifest.sources}
        if len(source_entries) != len(manifest.sources):
            raise PreparedDataError(
                "Prepared manifest contains duplicate source entries"
            )
        official_identity = (
            manifest.source_repository == SOURCE_REPOSITORY
            or manifest.source_commit == SOURCE_COMMIT
        )
        if official_identity:
            if (
                manifest.source_repository != SOURCE_REPOSITORY
                or manifest.source_commit != SOURCE_COMMIT
            ):
                raise PreparedDataError(
                    "Official prepared-data source repository and commit must match "
                    "the pinned pair"
                )
            expected_sources = {item.name: item for item in SOURCE_FILES}
            if set(source_entries) != set(expected_sources):
                raise PreparedDataError(
                    "Official prepared manifest does not declare the exact pinned "
                    "source-file set"
                )
            for filename, expected in expected_sources.items():
                entry = source_entries[filename]
                if (
                    entry.sha256 != expected.sha256
                    or entry.size_bytes != expected.size_bytes
                ):
                    raise PreparedDataError(
                        f"Official source identity mismatch for {filename}"
                    )
        elif (
            manifest.source_repository == "whyback/synthetic-fixture"
            and manifest.source_commit == "whyback-synthetic-fixture-v1"
        ):
            if manifest.sources:
                raise PreparedDataError(
                    "Synthetic fixture manifests cannot claim external source files"
                )
        else:
            raise PreparedDataError(
                "Prepared manifest has an unsupported dataset source identity"
            )
        entries = {entry.table: entry for entry in manifest.prepared}
        if len(entries) != len(manifest.prepared):
            raise PreparedDataError(
                "Prepared manifest contains duplicate table entries"
            )
        for table in tables:
            entry = entries.get(table)
            expected_filename = TABLE_FILES[table]
            if entry is None or entry.filename != expected_filename:
                raise PreparedDataError(
                    f"Prepared manifest does not declare {expected_filename}"
                )
            path = self.prepared_dir / expected_filename
            actual_hash = sha256_file(path)
            if actual_hash != entry.sha256:
                raise PreparedDataError(
                    f"Prepared table hash mismatch for {expected_filename}: "
                    f"expected {entry.sha256}, got {actual_hash}"
                )
        return manifest

    def query(self, sql: str, parameters: Sequence[Any] | None = None) -> pd.DataFrame:
        """Execute parameterized analytical SQL and return a result boundary frame."""

        return self._connection.execute(sql, parameters or []).fetch_df()

    def scalar(self, sql: str, parameters: Sequence[Any] | None = None) -> Any:
        """Execute a query expected to yield one scalar value."""

        row = self._connection.execute(sql, parameters or []).fetchone()
        if row is None:
            return None
        return row[0]

    def table_count(self, table: str) -> int:
        """Return the row count of a known registered table."""

        if table not in TABLE_FILES:
            raise PreparedDataError(f"Unknown prepared table: {table}")
        return int(self.scalar(f"SELECT COUNT(*) FROM {table}"))

    def fork(self) -> DataRepository:
        """Open an independent connection over the same immutable tables.

        Tool attempts run on forks so a timed-out query can be interrupted without
        racing a retry or the owner connection used by the investigation.
        """

        return DataRepository(
            self.prepared_dir,
            required_tables=self._required_tables,
            validate_manifest=False,
        )

    def interrupt(self) -> None:
        """Request cancellation of the query currently using this connection."""

        self._connection.interrupt()

    def close(self) -> None:
        """Close this repository's DuckDB connection."""

        self._connection.close()

    def __enter__(self) -> DataRepository:
        """Return this open repository when entering a context manager."""

        return self

    def __exit__(self, *_: object) -> None:
        """Close the repository when its context exits."""

        self.close()
