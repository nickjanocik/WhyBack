"""Idempotent conversion of official R data into canonical Parquet tables."""

from __future__ import annotations

import gc
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Final

import duckdb
import pandas as pd
import pyreadr

from whyback.config import SOURCE_COMMIT
from whyback.data.contracts import normalize_frame, validate_relations
from whyback.data.download import SOURCE_FILES, verify_sources
from whyback.data.manifest import (
    PREPARATION_TRANSFORM_VERSION,
    DataManifest,
    SourceManifestEntry,
    new_manifest_timestamp,
    parquet_manifest_entry,
    preparation_code_sha256,
    read_manifest,
    write_manifest,
)

SOURCE_TABLES: Final[dict[str, str]] = {
    "transactions.rds": "transactions",
    "promotions.rds": "promotions",
    "products.rda": "products",
    "demographics.rda": "demographics",
    "campaigns.rda": "campaigns",
    "campaign_descriptions.rda": "campaign_descriptions",
    "coupons.rda": "coupons",
    "coupon_redemptions.rda": "coupon_redemptions",
}

BASE_DEFINITIONS: Final[dict[str, str]] = {
    "transactions": (
        "Normalized official transaction line items; sales_value renamed "
        "retailer_sales_value."
    ),
    "products": (
        "Unique product hierarchy with missing descriptive metadata mapped to UNKNOWN."
    ),
    "demographics": (
        "Normalized official household demographics; retained for context, not "
        "recommendation targeting."
    ),
    "campaigns": "Normalized official household campaign participation.",
    "campaign_descriptions": "Normalized campaign type and date ranges.",
    "coupons": (
        "Campaign coupon-to-product bridge after exact composite-key deduplication."
    ),
    "coupon_redemptions": "Normalized observed household coupon redemptions.",
}
PREPARED_TABLE_ORDER: Final = (
    "transactions",
    "products",
    "demographics",
    "campaigns",
    "campaign_descriptions",
    "coupons",
    "coupon_redemptions",
    "promotion_state",
    "household_week",
    "baskets",
)


def _read_r_frame(path: Path, table: str) -> pd.DataFrame:
    """Load one R object, preserving New York transaction timestamp semantics."""

    # The source stores transaction timestamps as epoch values described in
    # America/New_York local time. Pyreadr otherwise applies UTC and shifts
    # dates around midnight, corrupting active-day and cadence calculations.
    timezone = "America/New_York" if table == "transactions" else None
    objects = pyreadr.read_r(str(path), timezone=timezone)
    if len(objects) != 1:
        raise ValueError(
            f"Expected exactly one R object in {path}, found {len(objects)}"
        )
    return next(iter(objects.values()))


def _source_tree_identity() -> tuple[str, bool]:
    """Report the configured or Git-derived source revision and dirty status."""

    configured = os.getenv("WHYBACK_SOURCE_TREE_VERSION")
    if configured:
        return configured, os.getenv("WHYBACK_SOURCE_TREE_DIRTY") == "1"
    repository_root = Path(__file__).resolve().parents[3]
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
            cwd=repository_root,
        )
        status = subprocess.run(
            [
                "git",
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
                "--",
                ".",
                ":(exclude)artifacts",
                ":(exclude)data",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
            cwd=repository_root,
        )
    except (OSError, subprocess.SubprocessError):
        return "unavailable", True
    return revision.stdout.strip() or "unavailable", bool(status.stdout.strip())


def _write_parquet(frame: pd.DataFrame, path: Path) -> None:
    """Write a Zstandard-compressed frame to a temporary file, then publish it."""

    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_parquet(temporary, index=False, compression="zstd")
    temporary.replace(path)


def _sql_path(path: Path) -> str:
    """Resolve a path and escape apostrophes for a DuckDB SQL string literal."""

    return str(path.resolve()).replace("'", "''")


def _copy_query(connection: duckdb.DuckDBPyConnection, query: str, path: Path) -> None:
    """Run a query into compressed Parquet and atomically publish the result."""

    temporary = path.with_suffix(path.suffix + ".tmp")
    destination = _sql_path(temporary)
    connection.execute(
        f"COPY ({query}) TO '{destination}' (FORMAT PARQUET, COMPRESSION ZSTD)"
    )
    temporary.replace(path)


def _build_derived_tables(prepared_dir: Path) -> dict[str, str]:
    """Build deterministic household-week and basket tables and their definitions."""

    transactions_path = _sql_path(prepared_dir / "transactions.parquet")
    products_path = _sql_path(prepared_dir / "products.parquet")
    definitions = {
        "promotion_state": (
            "One row per product_id, store_id, week; location presence is "
            "OR-aggregated and nonzero codes are sorted into explicit lists."
        ),
        "household_week": (
            "Transaction line items grouped by household_id and week with retailer "
            "sales value, units, baskets, and active transaction days."
        ),
        "baskets": (
            "Transaction line items grouped by household_id and basket_id with "
            "store/week, retailer sales value, units, products, categories, and "
            "timestamps."
        ),
    }
    connection = duckdb.connect()
    try:
        household_week_query = f"""
            SELECT household_id, week,
                   SUM(retailer_sales_value)::DOUBLE AS retailer_sales_value,
                   SUM(quantity)::DOUBLE AS units,
                   COUNT(DISTINCT basket_id)::BIGINT AS distinct_baskets,
                   COUNT(DISTINCT CAST(transaction_timestamp AS DATE))::BIGINT
                       AS active_days
            FROM read_parquet('{transactions_path}')
            GROUP BY household_id, week
            ORDER BY household_id, week
        """
        _copy_query(
            connection,
            household_week_query,
            prepared_dir / "household_week.parquet",
        )

        baskets_query = f"""
            SELECT t.household_id, t.basket_id,
                   MIN(t.store_id) AS store_id,
                   MIN(t.week)::SMALLINT AS week,
                   MIN(t.transaction_timestamp) AS transaction_timestamp,
                   SUM(t.retailer_sales_value)::DOUBLE AS retailer_sales_value,
                   SUM(t.quantity)::DOUBLE AS units,
                   COUNT(DISTINCT t.product_id)::BIGINT AS distinct_products,
                   COUNT(DISTINCT COALESCE(p.product_category, 'UNKNOWN'))::BIGINT
                       AS distinct_categories
            FROM read_parquet('{transactions_path}') t
            LEFT JOIN read_parquet('{products_path}') p USING (product_id)
            GROUP BY t.household_id, t.basket_id
            ORDER BY t.household_id, transaction_timestamp, t.basket_id
        """
        _copy_query(connection, baskets_query, prepared_dir / "baskets.parquet")
    finally:
        connection.close()
    return definitions


def _write_promotion_state(frame: pd.DataFrame, prepared_dir: Path) -> str:
    """Collapse promotion rows to canonical product-store-week availability state."""

    path = prepared_dir / "promotion_state.parquet"
    connection = duckdb.connect()
    try:
        connection.register("promotion_source", frame)
        query = """
            SELECT product_id, store_id, week,
                   BOOL_OR(display_location <> '0') AS any_display,
                   BOOL_OR(mailer_location <> '0') AS any_mailer,
                   COALESCE(
                       STRING_AGG(
                           DISTINCT display_location,
                           '|' ORDER BY display_location
                       )
                           FILTER (WHERE display_location <> '0'),
                       ''
                   ) AS display_locations,
                   COALESCE(
                       STRING_AGG(
                           DISTINCT mailer_location,
                           '|' ORDER BY mailer_location
                       )
                           FILTER (WHERE mailer_location <> '0'),
                       ''
                   ) AS mailer_locations
            FROM promotion_source
            GROUP BY product_id, store_id, week
            ORDER BY product_id, store_id, week
        """
        _copy_query(connection, query, path)
    finally:
        connection.close()
    return (
        "One row per product_id, store_id, week; location presence is OR-aggregated "
        "and nonzero codes are sorted into explicit lists."
    )


def manifest_is_current(manifest_path: Path, raw_dir: Path, prepared_dir: Path) -> bool:
    """Return true only when source and every prepared hash still match."""

    if not manifest_path.is_file():
        return False
    try:
        manifest = read_manifest(manifest_path)
        actual_sources = verify_sources(raw_dir)
    except (ValueError, OSError):
        return False
    if (
        manifest.preparation_transform_version != PREPARATION_TRANSFORM_VERSION
        or manifest.preparation_code_sha256 != preparation_code_sha256()
        or manifest.source_commit != SOURCE_COMMIT
    ):
        return False
    expected_sources = {entry.filename: entry.sha256 for entry in manifest.sources}
    if actual_sources != expected_sources:
        return False
    for entry in manifest.prepared:
        path = prepared_dir / entry.filename
        if not path.is_file():
            return False
        from whyback.data.download import sha256_file

        if sha256_file(path) != entry.sha256:
            return False
    return True


def prepare_data(
    raw_dir: Path,
    prepared_dir: Path,
    *,
    force: bool = False,
) -> DataManifest:
    """Validate and prepare all pinned source files, reusing a valid manifest."""

    manifest_path = prepared_dir / "manifest.json"
    if not force and manifest_is_current(manifest_path, raw_dir, prepared_dir):
        return read_manifest(manifest_path)

    verified_hashes = verify_sources(raw_dir)
    prepared_dir.mkdir(parents=True, exist_ok=True)
    normalized: dict[str, pd.DataFrame] = {}
    source_entries: list[SourceManifestEntry] = []

    for source in SOURCE_FILES:
        table = SOURCE_TABLES[source.name]
        source_frame = _read_r_frame(raw_dir / source.name, table)
        source_entries.append(
            SourceManifestEntry(
                filename=source.name,
                sha256=verified_hashes[source.name],
                size_bytes=source.size_bytes,
                row_count=len(source_frame),
                schema_summary={
                    str(column): str(dtype)
                    for column, dtype in source_frame.dtypes.items()
                },
                missing_values={
                    str(column): int(count)
                    for column, count in source_frame.isna().sum().items()
                },
            )
        )
        frame = normalize_frame(table, source_frame)
        if table == "coupons":
            frame = frame.drop_duplicates(
                ["coupon_upc", "campaign_id", "product_id"]
            ).reset_index(drop=True)
        normalized[table] = frame

    diagnostics: dict[str, float | int | str] = dict(validate_relations(normalized))
    promotion_definition = _write_promotion_state(
        normalized.pop("promotions"), prepared_dir
    )
    gc.collect()

    for table, frame in normalized.items():
        _write_parquet(frame, prepared_dir / f"{table}.parquet")

    derived_definitions = _build_derived_tables(prepared_dir)
    definitions = {
        **BASE_DEFINITIONS,
        **derived_definitions,
        "promotion_state": promotion_definition,
    }
    prepared_entries = tuple(
        parquet_manifest_entry(
            table, prepared_dir / f"{table}.parquet", definitions[table]
        )
        for table in PREPARED_TABLE_ORDER
    )
    diagnostics["promotion_state_rows"] = next(
        entry.row_count
        for entry in prepared_entries
        if entry.table == "promotion_state"
    )
    diagnostics["promotion_rows_collapsed"] = int(diagnostics["promotion_rows"]) - int(
        diagnostics["promotion_state_rows"]
    )
    source_tree_version, source_tree_dirty = _source_tree_identity()
    manifest = DataManifest(
        preparation_timestamp=new_manifest_timestamp(),
        preparation_code_sha256=preparation_code_sha256(),
        source_tree_version=source_tree_version,
        source_tree_dirty=source_tree_dirty,
        sources=tuple(source_entries),
        prepared=prepared_entries,
        diagnostics=diagnostics,
    )
    write_manifest(manifest, manifest_path)
    return manifest


def prepare_frames_for_tests(
    frames: Mapping[str, pd.DataFrame], prepared_dir: Path
) -> None:
    """Prepare already-loaded contract-shaped frames for deterministic tests."""

    prepared_dir.mkdir(parents=True, exist_ok=True)
    normalized = {
        table: normalize_frame(table, frame) for table, frame in frames.items()
    }
    normalized["coupons"] = normalized["coupons"].drop_duplicates(
        ["coupon_upc", "campaign_id", "product_id"]
    )
    diagnostics: dict[str, float | int | str] = dict(validate_relations(normalized))
    promotion_definition = _write_promotion_state(
        normalized.pop("promotions"), prepared_dir
    )
    for table, frame in normalized.items():
        _write_parquet(frame, prepared_dir / f"{table}.parquet")
    derived_definitions = _build_derived_tables(prepared_dir)
    definitions = {
        **BASE_DEFINITIONS,
        **derived_definitions,
        "promotion_state": promotion_definition,
    }
    prepared_entries = tuple(
        parquet_manifest_entry(
            table,
            prepared_dir / f"{table}.parquet",
            definitions[table],
        )
        for table in PREPARED_TABLE_ORDER
    )
    diagnostics["promotion_state_rows"] = next(
        entry.row_count
        for entry in prepared_entries
        if entry.table == "promotion_state"
    )
    diagnostics["promotion_rows_collapsed"] = int(diagnostics["promotion_rows"]) - int(
        diagnostics["promotion_state_rows"]
    )
    write_manifest(
        DataManifest(
            source_repository="whyback/synthetic-fixture",
            source_commit="whyback-synthetic-fixture-v1",
            preparation_timestamp=new_manifest_timestamp(),
            preparation_code_sha256=preparation_code_sha256(),
            source_tree_version="synthetic-fixture",
            source_tree_dirty=False,
            sources=(),
            prepared=prepared_entries,
            diagnostics=diagnostics,
        ),
        prepared_dir / "manifest.json",
    )
