"""Anlagen aus dem Ratsinformationssystem holen, ohne den Server zu fluten.

Das RIS sperrt bei zu vielen Anfragen das ganze Netzwerk ("Zu viele Zugriffe aus
Ihrem Netzwerk, Zugriff temporär gesperrt") und liefert dann eine Fehlerseite mit
HTTP 200 statt der Datei. Diese Tests halten die Gegenmaßnahmen fest: die
Vorlagenseite wird pro Lauf höchstens einmal geladen, die Links werden von dort
gelesen statt aus sources.yaml, und eine Fehlerseite wird als solche erkannt.
"""

from __future__ import annotations

import pytest

from pipeline.fetch.fetch import RisSession, attachment_index

PAGE = "https://www.roedermark.sitzung-online.de/public/vo020?VOLFDNR=1000940"

def _link(index: int) -> str:
    return (
        f'<a href="./vo020?0--anlagenHeaderPanel-attachmentsList-{index}'
        f'-attachment-link&amp;VOLFDNR=1000940">Anlage {index}</a>'
    )


# Absichtlich nicht in Index-Reihenfolge – die Reihenfolge im HTML ist nicht garantiert.
VORLAGE_HTML = (
    "<html><body>"
    + _link(1) + _link(0) + _link(2)
    + '<a href="./si010">unrelated</a>'
    + "</body></html>"
)

# Was der Server liefert, wenn er dichtmacht: HTTP 200, aber keine Anlagen.
RATE_LIMITED_HTML = """
<html><body><h1>Es ist ein Fehler aufgetreten</h1>
<p>Zu viele Zugriffe aus Ihrem Netzwerk, Zugriff temporär gesperrt.</p></body></html>
"""


class FakeResponse:
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self) -> None:
        pass


class CountingSession:
    """Zählt, wie oft die Vorlagenseite tatsächlich angefragt wird."""

    def __init__(self, text: str):
        self.text = text
        self.calls: list[str] = []

    def get(self, url: str, **kwargs) -> FakeResponse:
        self.calls.append(url)
        return FakeResponse(self.text)

    def close(self) -> None:
        pass


@pytest.fixture
def ris() -> RisSession:
    session = RisSession(delay=0)
    session.session = CountingSession(VORLAGE_HTML)
    return session


def test_links_are_resolved_from_the_page_in_index_order(ris):
    links = ris.attachment_links(PAGE)
    assert len(links) == 3
    for i, link in enumerate(links):
        assert f"attachmentsList-{i}-attachment-link" in link
    # &amp; aus dem HTML muss zu & werden, sonst geht die Anfrage ins Leere
    assert "&amp;" not in links[0]
    assert links[0].startswith("https://www.roedermark.sitzung-online.de/public/")


def test_the_page_is_fetched_at_most_once_per_run(ris):
    for _ in range(5):
        ris.attachment_links(PAGE)
    assert ris.session.calls == [PAGE], "die Vorlagenseite darf nur einmal geladen werden"


def test_download_attachment_reuses_the_cached_page(ris, tmp_path, monkeypatch):
    got: list[str] = []
    monkeypatch.setattr(RisSession, "_get_pdf", lambda self, url, dest: got.append(url) or 200)
    for i in range(3):
        ris.download_attachment(PAGE, i, tmp_path / f"{i}.pdf")
    assert len(ris.session.calls) == 1
    assert len(got) == 3


def test_a_rate_limited_page_fails_loudly(tmp_path):
    """Wenn der Server dichtmacht, darf das nicht als 'keine Anlagen' durchgehen."""
    session = RisSession(delay=0)
    session.session = CountingSession(RATE_LIMITED_HTML)
    with pytest.raises(ValueError, match="No attachment links"):
        session.attachment_links(PAGE)


def test_asking_past_the_end_is_an_error(ris, tmp_path):
    with pytest.raises(IndexError):
        ris.download_attachment(PAGE, 99, tmp_path / "x.pdf")


def test_attachment_index_prefers_the_explicit_field():
    assert attachment_index({"document_id": "x", "attachment_index": 7, "url": "…-3-…"}) == 7


def test_attachment_index_falls_back_to_the_stored_url():
    doc = {
        "document_id": "x",
        "url": "https://h/vo020?0--anlagenHeaderPanel-attachmentsList-4-attachment-link&V=1",
    }
    assert attachment_index(doc) == 4


def test_attachment_index_without_any_hint_is_an_error():
    with pytest.raises(ValueError, match="attachment_index"):
        attachment_index({"document_id": "x", "url": "https://h/plain.pdf"})
