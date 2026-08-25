"""Prepared-data manifest models and hashing helpers."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal

import pyarrow.parquet as pq
from pydantic import BaseModel, ConfigDict, Field

from whyback import __version__
from whyback.config import SOURCE_COMMIT, SOURCE_REPOSITORY
from whyback.data.download import sha256_file

PREPARATION_TRANSFORM_VERSION: Final = "whyback-complete-journey-v1"
_PREPARATION_CODE_FILES: Final = (
    Path(__file__).with_name("contracts.py"),
    Path(__file__),
    Path(__file__).with_name("prepare.py"),
)


def preparation_code_sha256() -> str:
    """Hash the exact modules that define canonical preparation semantics."""

    digest = hashlib.sha256()
    for path in sorted(_PREPARATION_CODE_FILES, key=lambda item: item.name):
        name = path.name.encode()
        digest.update(len(name).to_bytes(8, "big"))
        digest.update(name)
        digest.update(path.read_bytes())
    return digest.hexdigest()


class SourceManifestEntry(BaseModel):
    """Verified identity and observed schema of one official source file."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    filename: str
    sha256: str
    size_bytes: int = Field(ge=0)
    row_count: int = Field(ge=0)
    schema_summary: dict[str, str]
    missing_values: dict[str, int]


class PreparedManifestEntry(BaseModel):
    """Identity and schema of one canonical Parquet table."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    table: str
    filename: str
    sha256: str
    size_bytes: int = Field(ge=0)
    row_count: int = Field(ge=0)
    schema_summary: dict[str, str]
    definition: str


class DataManifest(BaseModel):
    """Replayable provenance for a complete preparation run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    manifest_version: Literal[2] = 2
    source_repository: str = SOURCE_REPOSITORY
    source_commit: str = SOURCE_COMMIT
    preparation_timestamp: datetime
    application_version: str = __version__
    preparation_transform_version: Literal["whyback-complete-journey-v1"] = (
        PREPARATION_TRANSFORM_VERSION
    )
    preparation_code_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_tree_version: str
    source_tree_dirty: bool
    sources: tuple[SourceManifestEntry, ...]
    prepared: tuple[PreparedManifestEntry, ...]
    diagnostics: dict[str, float | int | str]


def parquet_manifest_entry(
    table: str,
    path: Path,
    definition: str,
) -> PreparedManifestEntry:
    """Inspect a Parquet file without loading its rows."""

    metadata = pq.read_metadata(path)
    arrow_schema = pq.read_schema(path)
    return PreparedManifestEntry(
        table=table,
        filename=path.name,
        sha256=sha256_file(path),
        size_bytes=path.stat().st_size,
        row_count=metadata.num_rows,
        schema_summary={field.name: str(field.type) for field in arrow_schema},
        definition=definition,
    )


def write_manifest(manifest: DataManifest, path: Path) -> None:
    """Atomically write stable, human-readable manifest JSON."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def read_manifest(path: Path) -> DataManifest:
    """Parse and validate a data manifest."""

    return DataManifest.model_validate_json(path.read_text(encoding="utf-8"))


def new_manifest_timestamp() -> datetime:
    """Return an aware UTC timestamp through a testable helper."""

    return datetime.now(UTC)
