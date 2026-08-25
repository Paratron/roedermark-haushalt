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
import re
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


class RisSession:
    """One shared session for all attachments of a council information system page.

    Attachments in ALLRIS/SessionNet are not plain files: their links are stateful
    Wicket links that only resolve against server-side page state, so the parent
    page has to be loaded first. Doing that per attachment means two requests each
    and re-downloading the same ~50 KB page over and over – enough to get the whole
    network temporarily blocked ("Zu viele Zugriffe aus Ihrem Netzwerk"). This
    loads each parent page at most once per run, caches the resolved links, and
    never stores them in sources.yaml, where they would go stale.
    """

    ATTACHMENT_RE = re.compile(
        r'href="\./(vo020\?[^"]*attachmentsList-(\d+)-attachment-link[^"]*)"'
    )

    def __init__(self, *, timeout: int = REQUEST_TIMEOUT, delay: float = DELAY_SECONDS):
        self.session = requests.Session()
        self.timeout = timeout
        self.delay = delay
        self._links: dict[str, list[str]] = {}

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> RisSession:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def attachment_links(self, page_url: str) -> list[str]:
        """Resolve the current attachment links of *page_url*, loading it at most once."""
        if page_url not in self._links:
            logger.info("RIS page: %s", page_url)
            resp = self.session.get(page_url, timeout=self.timeout)
            resp.raise_for_status()
            base = page_url.rsplit("/", 1)[0] + "/"
            found = {
                int(idx): base + href.replace("&amp;", "&")
                for href, idx in self.ATTACHMENT_RE.findall(resp.text)
            }
            if not found:
                raise ValueError(
                    f"No attachment links found on {page_url} – the page may be rate "
                    f"limiting us, or the Vorlage no longer carries attachments."
                )
            self._links[page_url] = [found[i] for i in sorted(found)]
            time.sleep(self.delay)
        return self._links[page_url]

    def download_attachment(self, page_url: str, index: int, dest: Path) -> int:
        links = self.attachment_links(page_url)
        if index >= len(links):
            raise IndexError(
                f"Attachment {index} requested but {page_url} lists only {len(links)}"
            )
        return self._get_pdf(links[index], dest)

    def download(self, url: str, dest: Path) -> int:
        return self._get_pdf(url, dest)

    def _get_pdf(self, url: str, dest: Path) -> int:
        resp = self.session.get(url, stream=True, timeout=self.timeout, allow_redirects=True)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        if "pdf" not in content_type.lower():
            # A stale or rate-limited link answers with an HTML page, not the file.
            raise ValueError(
                f"Expected a PDF but got Content-Type {content_type!r} for {url}"
            )

        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                f.write(chunk)
        return resp.status_code


def download_pdf(
    url: str,
    dest: Path,
    *,
    timeout: int = REQUEST_TIMEOUT,
    ris: RisSession | None = None,
) -> int:
    """Download *url* to *dest*. Returns HTTP status code."""
    if ris is not None:
        return ris.download(url, dest)
    with RisSession(timeout=timeout) as session:
        return session.download(url, dest)


# ── main logic ────────────────────────────────────────────────────────


def attachment_index(doc: dict) -> int:
    """Position of a council-information-system attachment on its Vorlage page.

    Taken from `attachment_index:` in sources.yaml, or parsed out of the stored
    URL for entries written before that field existed.
    """
    if "attachment_index" in doc:
        return int(doc["attachment_index"])
    m = re.search(r"attachmentsList-(\d+)-attachment-link", doc.get("url", ""))
    if not m:
        raise ValueError(
            f"{doc['document_id']}: session_url is set but no attachment_index "
            f"and none derivable from url"
        )
    return int(m.group(1))


def load_sources(path: Path) -> list[dict]:
    """Parse sources.yaml and return the documents list."""
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("documents", [])


def build_documents_index(out_dir: Path) -> dict:
    """Load existing documents.json (if any) into a dict keyed by document_id."""
    index_path = out_dir / "documents.json"
    if index_path.exists():
        with open(index_path, encoding="utf-8") as f:
            items = json.load(f)
        return {d["document_id"]: d for d in items}
    return {}


def save_documents_index(index: dict, out_dir: Path) -> None:
    """Persist documents.json (sorted by document_id)."""
    items = sorted(index.values(), key=lambda d: d["document_id"])
    index_path = out_dir / "documents.json"
    with open(index_path, "w", encoding="utf-8") as f:
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

    stats = {"downloaded": 0, "skipped": 0, "failed": 0, "duplicate": 0, "adopted": 0}

    ris = RisSession()
    try:
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

            # A file on disk that the index does not know about yet – adopt it
            # instead of re-requesting it. Matters for the council information
            # system, which rate-limits and blocks the whole network when hit
            # repeatedly; a failed run must not turn into a download loop.
            adopted = not force and dest.exists()
            if adopted:
                logger.info("ADOPT %s (already on disk, not re-downloading)", doc_id)
                stats["adopted"] += 1
            else:
                logger.info("FETCH %s  ←  %s", doc_id, url)
                try:
                    if doc.get("session_url"):
                        # Link resolved live from the Vorlage page: the one stored in
                        # sources.yaml is session-bound and goes stale.
                        ris.download_attachment(
                            doc["session_url"], attachment_index(doc), dest
                        )
                    else:
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

            if adopted:
                # Nothing was requested – no counter to bump, no delay to observe.
                continue

            stats["downloaded"] += 1

            # Polite delay
            time.sleep(DELAY_SECONDS)

    finally:
        ris.close()

    save_documents_index(index, out_dir)

    logger.info(
        "Done – downloaded: %d, adopted: %d, skipped: %d, failed: %d, duplicates: %d",
        stats["downloaded"],
        stats["adopted"],
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
