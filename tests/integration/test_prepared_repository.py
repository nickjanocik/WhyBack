from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.fixtures.source_frames import minimal_source_frames
from whyback.data.prepare import prepare_frames_for_tests
from whyback.data.repository import DataRepository, PreparedDataError


def test_preparation_builds_canonical_views_without_economic_multiplication(
    tmp_path: Path,
) -> None:
    frames = minimal_source_frames()
    frames["coupons"].loc[len(frames["coupons"])] = frames["coupons"].iloc[0]
    prepare_frames_for_tests(frames, tmp_path)

    with DataRepository(
        tmp_path,
        required_tables=(
            "transactions",
            "products",
            "coupons",
            "promotion_state",
            "household_week",
            "baskets",
        ),
    ) as repository:
        promotion = repository.query("SELECT * FROM promotion_state")
        original_total = repository.scalar(
            "SELECT SUM(retailer_sales_value) FROM transactions"
        )
        enriched_total = repository.scalar(
            """
            SELECT SUM(t.retailer_sales_value)
            FROM transactions t
            LEFT JOIN promotion_state p USING (product_id, store_id, week)
            """
        )

        assert len(promotion) == 1
        assert bool(promotion.iloc[0]["any_display"])
        assert bool(promotion.iloc[0]["any_mailer"])
        assert promotion.iloc[0]["display_locations"] == "3|5"
        assert promotion.iloc[0]["mailer_locations"] == "A"
        assert enriched_total == original_total == 12.0
        assert repository.table_count("baskets") == 2
        assert repository.table_count("household_week") == 2
        assert repository.table_count("products") == 2
        assert repository.table_count("coupons") == 1


def test_repository_fails_when_required_table_is_missing(tmp_path: Path) -> None:
    try:
        DataRepository(tmp_path, required_tables=("transactions",))
    except PreparedDataError as error:
        assert "transactions.parquet" in str(error)
    else:  # pragma: no cover - defensive assertion with a clearer failure
        raise AssertionError("Expected missing prepared table to fail")


def test_repository_rejects_a_prepared_table_changed_after_manifest(
    tmp_path: Path,
) -> None:
    prepare_frames_for_tests(minimal_source_frames(), tmp_path)
    transactions = tmp_path / "transactions.parquet"
    transactions.write_bytes(transactions.read_bytes() + b"tampered")

    with pytest.raises(PreparedDataError, match="hash mismatch"):
        DataRepository(tmp_path, required_tables=("transactions",))


def test_repository_rejects_forged_official_source_provenance(tmp_path: Path) -> None:
    prepare_frames_for_tests(minimal_source_frames(), tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_repository"] = "bradleyboehmke/completejourney"
    manifest["source_commit"] = "5b5d06192b9856edd04e4d405787af2f2e4a1fef"
    manifest["sources"] = []
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(PreparedDataError, match="exact pinned source-file set"):
        DataRepository(tmp_path, required_tables=("transactions",))
