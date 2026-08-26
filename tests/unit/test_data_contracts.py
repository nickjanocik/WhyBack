"""Tests for WhyBack's data contracts behavior."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pytest

import whyback.data.download as download_module
from tests.fixtures.source_frames import minimal_source_frames
from whyback.data.contracts import (
    DataContractError,
    normalize_frame,
    validate_relations,
)
from whyback.data.download import SourceFile, SourceHashMismatchError, download_sources


def test_product_metadata_is_explicitly_unknown() -> None:
    """Verify that product metadata is explicitly unknown."""

    products = normalize_frame("products", minimal_source_frames()["products"])

    unmapped = products.loc[products["product_id"] == "2000"].iloc[0]
    assert unmapped["product_category"] == "UNKNOWN"
    assert unmapped["product_type"] == "UNKNOWN"
    assert unmapped["package_size"] == "UNKNOWN"


def test_invalid_week_fails_preflight() -> None:
    """Verify that invalid week fails preflight."""

    transactions = minimal_source_frames()["transactions"]
    transactions.loc[0, "week"] = 54

    with pytest.raises(DataContractError, match=r"within 1\.\.53"):
        normalize_frame("transactions", transactions)


def test_relation_diagnostics_surface_promotion_multiplicity() -> None:
    """Verify that relation diagnostics surface promotion multiplicity."""

    frames = {
        table: normalize_frame(table, frame)
        for table, frame in minimal_source_frames().items()
    }

    diagnostics = validate_relations(frames)

    assert diagnostics["promotion_duplicate_key_rows"] == 2
    assert diagnostics["transaction_product_mapping_coverage"] == 1.0


def test_download_is_atomic_and_hash_verified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that download is atomic and hash verified."""

    content = b"official-pinned-bytes"
    source = SourceFile("tiny.rds", hashlib.sha256(content).hexdigest(), len(content))
    monkeypatch.setattr(download_module, "SOURCE_FILES", (source,))

    result = download_sources(tmp_path, open_url=lambda _: io.BytesIO(content))

    assert result == {"tiny.rds": source.sha256}
    assert (tmp_path / "tiny.rds").read_bytes() == content
    assert not (tmp_path / "tiny.rds.part").exists()


def test_download_removes_bad_partial_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that download removes bad partial file."""

    source = SourceFile("tiny.rds", "0" * 64, 3)
    monkeypatch.setattr(download_module, "SOURCE_FILES", (source,))

    with pytest.raises(SourceHashMismatchError):
        download_sources(tmp_path, open_url=lambda _: io.BytesIO(b"bad"))

    assert not (tmp_path / "tiny.rds").exists()
    assert not (tmp_path / "tiny.rds.part").exists()


def test_nonfinite_transaction_measure_is_rejected() -> None:
    """Verify that nonfinite transaction measure is rejected."""

    transactions = minimal_source_frames()["transactions"]
    transactions.loc[0, "sales_value"] = float("nan")

    with pytest.raises(DataContractError, match="non-finite"):
        normalize_frame("transactions", transactions)


def test_missing_promotion_code_is_not_silently_treated_as_zero() -> None:
    """Verify that missing promotion code is not silently treated as zero."""

    promotions = minimal_source_frames()["promotions"]
    promotions.loc[0, "display_location"] = None

    with pytest.raises(DataContractError, match="cannot be missing"):
        normalize_frame("promotions", promotions)
