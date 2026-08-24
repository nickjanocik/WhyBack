"""Source schema normalization and deterministic preflight checks."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd


class DataContractError(ValueError):
    """Prepared source data violates an explicit analytical contract."""


@dataclass(frozen=True, slots=True)
class TableContract:
    """Required source fields for one logical table."""

    required_columns: frozenset[str]
    identifier_columns: tuple[str, ...] = ()
    numeric_columns: tuple[str, ...] = ()


CONTRACTS: Mapping[str, TableContract] = {
    "transactions": TableContract(
        frozenset(
            {
                "household_id",
                "store_id",
                "basket_id",
                "product_id",
                "quantity",
                "sales_value",
                "retail_disc",
                "coupon_disc",
                "coupon_match_disc",
                "week",
                "transaction_timestamp",
            }
        ),
        ("household_id", "store_id", "basket_id", "product_id"),
        (
            "quantity",
            "sales_value",
            "retail_disc",
            "coupon_disc",
            "coupon_match_disc",
            "week",
        ),
    ),
    "promotions": TableContract(
        frozenset(
            {"product_id", "store_id", "display_location", "mailer_location", "week"}
        ),
        ("product_id", "store_id"),
        ("week",),
    ),
    "products": TableContract(
        frozenset(
            {
                "product_id",
                "manufacturer_id",
                "department",
                "brand",
                "product_category",
                "product_type",
                "package_size",
            }
        ),
        ("product_id", "manufacturer_id"),
    ),
    "demographics": TableContract(
        frozenset({"household_id"}),
        ("household_id",),
    ),
    "campaigns": TableContract(
        frozenset({"campaign_id", "household_id"}),
        ("campaign_id", "household_id"),
    ),
    "campaign_descriptions": TableContract(
        frozenset({"campaign_id", "campaign_type", "start_date", "end_date"}),
        ("campaign_id",),
    ),
    "coupons": TableContract(
        frozenset({"coupon_upc", "product_id", "campaign_id"}),
        ("coupon_upc", "product_id", "campaign_id"),
    ),
    "coupon_redemptions": TableContract(
        frozenset({"household_id", "coupon_upc", "campaign_id", "redemption_date"}),
        ("household_id", "coupon_upc", "campaign_id"),
    ),
}


def normalize_identifier(value: object) -> str:
    """Normalize identifiers without losing large integer precision."""

    if value is None or value is pd.NA:
        raise DataContractError("Identifier values cannot be missing")
    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            raise DataContractError(f"Invalid numeric identifier: {value!r}")
        return str(int(value))
    text = str(value).strip()
    if not text:
        raise DataContractError("Identifier values cannot be blank")
    if text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]
    return text


def _normalize_identifiers(frame: pd.DataFrame, columns: tuple[str, ...]) -> None:
    for column in columns:
        frame[column] = frame[column].map(normalize_identifier).astype("string")


def _normalize_numeric(frame: pd.DataFrame, columns: tuple[str, ...]) -> None:
    for column in columns:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
        values = frame[column].astype("float64")
        if not bool(np.isfinite(values.to_numpy()).all()):
            raise DataContractError(f"{column} contains a non-finite value")


def normalize_frame(table: str, source: pd.DataFrame) -> pd.DataFrame:
    """Return a normalized copy that satisfies the canonical column policy."""

    if table not in CONTRACTS:
        raise DataContractError(f"Unknown source table: {table}")
    contract = CONTRACTS[table]
    missing = contract.required_columns.difference(source.columns)
    if missing:
        raise DataContractError(f"{table} is missing columns: {sorted(missing)}")

    frame = source.copy()
    _normalize_identifiers(frame, contract.identifier_columns)
    _normalize_numeric(frame, contract.numeric_columns)

    if "week" in frame:
        weeks = frame["week"].astype("int16")
        if not bool(weeks.between(1, 53).all()):
            observed = (int(weeks.to_numpy().min()), int(weeks.to_numpy().max()))
            raise DataContractError(
                f"{table}.week must stay within 1..53; observed {observed}"
            )
        frame["week"] = weeks

    if table == "transactions":
        frame = frame.rename(
            columns={
                "sales_value": "retailer_sales_value",
                "retail_disc": "retail_discount",
                "coupon_disc": "coupon_discount",
                "coupon_match_disc": "coupon_match_discount",
            }
        )
        frame["transaction_timestamp"] = pd.to_datetime(
            frame["transaction_timestamp"], errors="raise"
        )
    elif table == "products":
        hierarchy = (
            "department",
            "brand",
            "product_category",
            "product_type",
            "package_size",
        )
        for column in hierarchy:
            frame[column] = frame[column].astype("string").fillna("UNKNOWN")
            frame.loc[frame[column].str.strip().eq(""), column] = "UNKNOWN"
        if frame["product_id"].duplicated().any():
            raise DataContractError("products.product_id must be unique")
    elif table == "promotions":
        for column in ("display_location", "mailer_location"):
            if bool(frame[column].isna().any()):
                raise DataContractError(
                    f"{table}.{column} cannot be missing; zero is an observed code"
                )
            frame[column] = frame[column].astype("string")
    elif table == "campaign_descriptions":
        campaign_types = frame["campaign_type"].astype("string")
        unknown_types = set(campaign_types.dropna().unique()).difference(
            {"Type A", "Type B", "Type C"}
        )
        if unknown_types:
            raise DataContractError(f"Unknown campaign types: {sorted(unknown_types)}")
        frame["campaign_type"] = campaign_types
        frame["start_date"] = pd.to_datetime(frame["start_date"], errors="raise")
        frame["end_date"] = pd.to_datetime(frame["end_date"], errors="raise")
    elif table == "coupon_redemptions":
        frame["redemption_date"] = pd.to_datetime(
            frame["redemption_date"], errors="raise"
        )

    return frame


def validate_relations(frames: Mapping[str, pd.DataFrame]) -> dict[str, float | int]:
    """Validate cross-table invariants and return material coverage diagnostics."""

    missing_tables = set(CONTRACTS).difference(frames)
    if missing_tables:
        raise DataContractError(f"Missing source tables: {sorted(missing_tables)}")

    transactions = frames["transactions"]
    products = frames["products"]
    promotions = frames["promotions"]
    transaction_products = set(transactions["product_id"].astype(str))
    product_ids = set(products["product_id"].astype(str))
    mapped = len(transaction_products.intersection(product_ids))
    product_coverage = (
        mapped / len(transaction_products) if transaction_products else 1.0
    )

    promotion_key_columns = ["product_id", "store_id", "week"]
    promotion_duplicate_rows = int(promotions.duplicated(promotion_key_columns).sum())
    return {
        "transaction_product_mapping_coverage": product_coverage,
        "promotion_duplicate_key_rows": promotion_duplicate_rows,
        "transaction_week_min": int(transactions["week"].to_numpy().min()),
        "transaction_week_max": int(transactions["week"].to_numpy().max()),
        "transaction_rows": len(transactions),
        "promotion_rows": len(promotions),
    }
