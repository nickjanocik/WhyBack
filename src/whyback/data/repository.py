"""Central DuckDB boundary for all deterministic analytical queries."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd


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
    return str(path.resolve()).replace("'", "''")


class DataRepository:
    """Own a DuckDB connection and registered read-only Parquet views."""

    def __init__(
        self,
        prepared_dir: Path,
        *,
        required_tables: Iterable[str] = TABLE_FILES,
    ) -> None:
        self.prepared_dir = prepared_dir
        self._connection = duckdb.connect()
        self._connection.execute("SET TimeZone = 'America/New_York'")
        tables = tuple(required_tables)
        unknown = set(tables).difference(TABLE_FILES)
        if unknown:
            self._connection.close()
            raise PreparedDataError(f"Unknown prepared tables: {sorted(unknown)}")
        try:
            for table in tables:
                path = prepared_dir / TABLE_FILES[table]
                if not path.is_file():
                    raise PreparedDataError(f"Prepared table is missing: {path}")
                self._connection.execute(
                    f"CREATE VIEW {table} AS SELECT * FROM "
                    f"read_parquet('{_quote_path(path)}')"
                )
        except Exception:
            self._connection.close()
            raise

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

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> DataRepository:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
