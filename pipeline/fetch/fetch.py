"""Fetch pipeline – download PDFs listed in sources.yaml and build documents.json.

Usage:
    python -m pipeline.fetch.fetch [--sources sources.yaml] [--out-dir data/raw]

Rules (from agents.md § 2):
  • Rate-limit requests (1 s between downloads)
  • Compute SHA-256 hash per file
  • Detect duplicates via hash
  • Never modify raw PDFs
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

logger = logging.getLogger(__name__)

# ── defaults ──────────────────────────────────────────────────────────

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_SOURCES = ROOT_DIR / "sources.yaml"
DEFAULT_OUT_DIR = ROOT_DIR / "data" / "raw"
DELAY_SECONDS = 1.0  # polite rate-limit
REQUEST_TIMEOUT = 120  # seconds (some PDFs are large)
CHUNK_SIZE = 8192


# ── helpers ───────────────────────────────────────────────────────────


def sha256_file(path: Path) -> str:
    """Return hex-encoded SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            h.update(chunk)
    return h.hexdigest()


def download_pdf(url: str, dest: Path, *, timeout: int = REQUEST_TIMEOUT) -> int:
    """Download *url* to *dest*. Returns HTTP status code."""
    resp = requests.get(url, stream=True, timeout=timeout, allow_redirects=True)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
            f.write(chunk)
    return resp.status_code


# ── main logic ────────────────────────────────────────────────────────


def load_sources(path: Path) -> list[dict]:
    """Parse sources.yaml and return the documents list."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return data.get("documents", [])


def build_documents_index(out_dir: Path) -> dict:
    """Load existing documents.json (if any) into a dict keyed by document_id."""
    index_path = out_dir / "documents.json"
    if index_path.exists():
        with open(index_path) as f:
            items = json.load(f)
        return {d["document_id"]: d for d in items}
    return {}


def save_documents_index(index: dict, out_dir: Path) -> None:
    """Persist documents.json (sorted by document_id)."""
    items = sorted(index.values(), key=lambda d: d["document_id"])
    index_path = out_dir / "documents.json"
    with open(index_path, "w") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
    logger.info("Wrote %s (%d documents)", index_path, len(items))


def fetch_all(
    sources_path: Path = DEFAULT_SOURCES,
    out_dir: Path = DEFAULT_OUT_DIR,
    *,
    force: bool = False,
) -> dict:
    """Download all PDFs from *sources_path* into *out_dir*.

    Parameters
    ----------
    force : bool
        Re-download even if file already exists (and hash matches).

    Returns
    -------
    dict  – the full documents index (document_id → metadata).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    docs = load_sources(sources_path)
    index = build_documents_index(out_dir)

    seen_hashes: dict[str, str] = {
        d["sha256"]: d["document_id"]
        for d in index.values()
        if "sha256" in d
    }

    stats = {"downloaded": 0, "skipped": 0, "failed": 0, "duplicate": 0}

    for doc in docs:
        doc_id = doc["document_id"]
        url = doc["url"]
        filename = f"{doc_id}.pdf"
        dest = out_dir / filename

        # Skip if already present (unless forced)
        if not force and dest.exists() and doc_id in index:
            logger.info("SKIP  %s (already exists)", doc_id)
            stats["skipped"] += 1
            continue

        logger.info("FETCH %s  ←  %s", doc_id, url)
        try:
            download_pdf(url, dest)
        except Exception:
            logger.exception("FAIL  %s", doc_id)
            stats["failed"] += 1
            continue

        file_hash = sha256_file(dest)
        file_size = dest.stat().st_size

        # Duplicate detection
        if file_hash in seen_hashes and seen_hashes[file_hash] != doc_id:
            logger.warning(
                "DUPLICATE hash: %s == %s (keeping both)",
                doc_id,
                seen_hashes[file_hash],
            )
            stats["duplicate"] += 1

        seen_hashes[file_hash] = doc_id

        index[doc_id] = {
            "document_id": doc_id,
            "doc_type": doc["doc_type"],
            "years": doc["years"],
            "priority": doc.get("priority", "primary"),
            "source_url": url,
            "filename": filename,
            "sha256": file_hash,
            "size_bytes": file_size,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

        stats["downloaded"] += 1

        # Polite delay
        time.sleep(DELAY_SECONDS)

    save_documents_index(index, out_dir)

    logger.info(
        "Done – downloaded: %d, skipped: %d, failed: %d, duplicates: %d",
        stats["downloaded"],
        stats["skipped"],
        stats["failed"],
        stats["duplicate"],
    )
    return index


# ── CLI ───────────────────────────────────────────────────────────────

def main() -> None:
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-5s  %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Fetch PDFs from sources.yaml")
    parser.add_argument(
        "--sources",
        type=Path,
        default=DEFAULT_SOURCES,
        help="Path to sources.yaml",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="Directory to save PDFs + documents.json",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if file exists",
    )
    args = parser.parse_args()

    fetch_all(sources_path=args.sources, out_dir=args.out_dir, force=args.force)


if __name__ == "__main__":
    main()
