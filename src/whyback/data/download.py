"""Download and verify the official pinned Complete Journey source files."""

from __future__ import annotations

import hashlib
import shutil
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from whyback.config import SOURCE_COMMIT, SOURCE_REPOSITORY


class SourceDataError(RuntimeError):
    """Base class for source acquisition failures."""


class MissingSourceError(SourceDataError):
    """A required source file is absent."""


class SourceHashMismatchError(SourceDataError):
    """A source file differs from the pinned byte content."""


@dataclass(frozen=True, slots=True)
class SourceFile:
    """Pinned source-file identity."""

    name: str
    sha256: str
    size_bytes: int

    @property
    def url(self) -> str:
        return (
            "https://raw.githubusercontent.com/"
            f"{SOURCE_REPOSITORY}/{SOURCE_COMMIT}/data/{self.name}"
        )


SOURCE_FILES: tuple[SourceFile, ...] = (
    SourceFile(
        "transactions.rds",
        "1fa0700033f1e5d9bb6b09e2be063d8d68474d346e95c50f2833e09d083e0007",
        12_775_661,
    ),
    SourceFile(
        "promotions.rds",
        "15a729fdad31b10d3afedb058da31bcd6e9e68cb0207a43b3121264cd80198ba",
        24_976_951,
    ),
    SourceFile(
        "products.rda",
        "a80c6df33623b4af296ae9f317a6647e369db7e8ce7e7baed0e1bf44b9d979e5",
        869_019,
    ),
    SourceFile(
        "demographics.rda",
        "8b80455bc841003b64e47f5e5c2221f6093b995e923d59e72a1f852c7e268980",
        4_237,
    ),
    SourceFile(
        "campaigns.rda",
        "33c7b3dc1bc722d465f97416fb1327c6a9a640190e464c73e354bce8c001a772",
        8_264,
    ),
    SourceFile(
        "campaign_descriptions.rda",
        "601bd17ea1a6de92cc288f393164813fbaf293b997d44054dcf1f3ebbe8dacee",
        496,
    ),
    SourceFile(
        "coupons.rda",
        "4d87effce5b8813c0934b581a83292707347577743320ca746878de89cc16f34",
        324_969,
    ),
    SourceFile(
        "coupon_redemptions.rda",
        "4b68148175ed19300bb2615d68d1a0300a5f971db3240819ab5d92e5919e1598",
        8_370,
    ),
)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Hash a file without loading it fully into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def verify_source_file(path: Path, source: SourceFile) -> str:
    """Verify exact size and SHA-256 for one pinned source file."""

    if not path.is_file():
        raise MissingSourceError(f"Required source file is missing: {path}")
    actual_size = path.stat().st_size
    if actual_size != source.size_bytes:
        raise SourceHashMismatchError(
            f"Size mismatch for {source.name}: expected {source.size_bytes}, "
            f"found {actual_size}"
        )
    actual_hash = sha256_file(path)
    if actual_hash != source.sha256:
        raise SourceHashMismatchError(
            f"SHA-256 mismatch for {source.name}: expected {source.sha256}, "
            f"found {actual_hash}"
        )
    return actual_hash


def verify_sources(raw_dir: Path) -> dict[str, str]:
    """Verify every required pinned file and return its hash by filename."""

    return {
        source.name: verify_source_file(raw_dir / source.name, source)
        for source in SOURCE_FILES
    }


OpenUrl = Callable[[str], BinaryIO]


def _open_url(url: str) -> BinaryIO:
    return urllib.request.urlopen(url, timeout=120)


def download_sources(
    raw_dir: Path,
    *,
    force: bool = False,
    open_url: OpenUrl = _open_url,
) -> dict[str, str]:
    """Idempotently download official files and atomically publish each one."""

    raw_dir.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, str] = {}
    for source in SOURCE_FILES:
        destination = raw_dir / source.name
        if destination.exists() and not force:
            hashes[source.name] = verify_source_file(destination, source)
            continue

        partial = destination.with_suffix(destination.suffix + ".part")
        try:
            with open_url(source.url) as response, partial.open("wb") as output:
                shutil.copyfileobj(response, output, length=1024 * 1024)
            hashes[source.name] = verify_source_file(partial, source)
            partial.replace(destination)
        except Exception:
            partial.unlink(missing_ok=True)
            raise
    return hashes
