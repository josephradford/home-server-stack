"""The reading-digest job: RSS feeds -> one EPUB dropped in the CWA ingest folder."""
from __future__ import annotations

import datetime
import html
import json
import logging
import os
from datetime import time
from pathlib import Path

import feedparser
from ebooklib import epub
from lxml.etree import tostring
from lxml.html import fromstring

from oddjobs.core.errors import OddJobsError
from oddjobs.jobs import JobContext, JobResult

log = logging.getLogger("oddjobs.digest")

MAX_PER_FEED = 20  # cap per feed per run, so the first run isn't a huge backlog

STYLE = """
body { font-family: serif; line-height: 1.5; margin: 1em; }
h1 { font-size: 1.4em; margin-bottom: 0.1em; }
h2 { font-size: 1.6em; border-bottom: 1px solid #999; padding-bottom: 0.2em; }
.byline { font-style: italic; color: #555; margin-top: 0; }
.byline a { color: #555; }
.note { background: #f4f4f4; border-left: 4px solid #c92a2a; padding: 0.6em 1em; }
"""


def to_xhtml(fragment: str) -> str:
    """Coerce a feed's (often not-quite-well-formed) HTML into valid XHTML.

    EPUB readers parse chapter content as strict XML — an unclosed <br> or
    <img> from a feed can silently truncate a chapter or break the whole
    file. Round-tripping through lxml's HTML parser (permissive) and
    re-serializing as XML fixes that. Falls back to escaped plain text if
    the fragment is too broken even for that.
    """
    if not fragment.strip():
        return ""
    try:
        node = fromstring(f"<div>{fragment}</div>")
        return tostring(node, encoding="unicode", method="xml")
    except Exception:  # noqa: BLE001
        return f"<p>{html.escape(fragment)}</p>"


def _write_atomic(path: Path, write) -> None:
    """Write via a temp file in the same dir so CWA's watcher never sees a partial EPUB."""
    tmp = path.with_name(path.name + ".tmp")
    try:
        write(tmp)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


class DigestJob:
    name = "digest"

    def __init__(self, run_at: time = time(5, 0)):
        self.run_at = run_at

    def run(self, ctx: JobContext) -> JobResult:
        if ctx.feeds_path is None or ctx.ingest_dir is None or ctx.data_dir is None:
            raise OddJobsError("digest is not configured (feeds, ingest and data paths required)")
        seen_path = ctx.data_dir / "digest-seen.json"
        seen = set(json.loads(seen_path.read_text())) if seen_path.exists() else set()
        urls = [
            line.strip()
            for line in ctx.feeds_path.read_text().splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

        by_source: dict[str, list[tuple[str, str, str, str]]] = {}  # source -> (title, link, author, body)
        truncated: dict[str, int] = {}  # source -> new posts beyond MAX_PER_FEED
        failed: list[str] = []

        for url in urls:
            try:
                response = ctx.client.get(url, follow_redirects=True, timeout=30)
                response.raise_for_status()
                feed = feedparser.parse(response.content)
                source = feed.feed.get("title", url)
                # Entries with neither id nor link have no stable identity for dedup;
                # skip them entirely rather than risk re-bundling them every run.
                new = [
                    e
                    for e in feed.entries
                    if (e.get("id") or e.get("link")) and (e.get("id") or e.get("link")) not in seen
                ]
                # Mark everything as seen, but only include the newest few.
                feed_keys = {e.get("id") or e.get("link") for e in feed.entries} - {None, ""}
                if len(new) > MAX_PER_FEED:
                    truncated[source] = len(new) - MAX_PER_FEED
                    log.info("%s: %d new, taking %d", source, len(new), MAX_PER_FEED)
                posts = []
                # Feeds list newest-first; reverse the batch so serialized work reads in order.
                for e in reversed(new[:MAX_PER_FEED]):
                    body = e.content[0].value if e.get("content") else e.get("summary", "")
                    posts.append((e.get("title", "Untitled"), e.get("link", ""), e.get("author", source), body))
                if posts:
                    by_source.setdefault(source, []).extend(posts)
                seen |= feed_keys
            except Exception as e:  # noqa: BLE001 - one bad feed must not stop the others
                log.warning("skipping %s: %s", url, e)
                failed.append(url)

        if urls and len(failed) == len(urls):
            raise OddJobsError(f"all {len(urls)} feeds failed")
        failure_note = f", {len(failed)} feed{'s' if len(failed) != 1 else ''} failed" if failed else ""

        ctx.data_dir.mkdir(parents=True, exist_ok=True)
        if not by_source:
            seen_path.write_text(json.dumps(sorted(seen)))
            return JobResult(detail="Nothing new" + failure_note)

        post_count = sum(len(v) for v in by_source.values())
        ctx.ingest_dir.mkdir(parents=True, exist_ok=True)
        today = datetime.date.today().isoformat()
        book = self._build_book(today, by_source, truncated, post_count)
        _write_atomic(
            ctx.ingest_dir / f"reading-{today}.epub", lambda tmp: epub.write_epub(str(tmp), book)
        )
        # State is saved only after the EPUB is in place, so a failed write retries next run.
        seen_path.write_text(json.dumps(sorted(seen)))
        return JobResult(detail=f"{post_count} posts from {len(by_source)} feeds{failure_note}")

    @staticmethod
    def _build_book(today, by_source, truncated, post_count) -> epub.EpubBook:
        book = epub.EpubBook()
        book.set_identifier(f"digest-{today}")
        book.set_title(f"Reading list {today}")
        book.set_language("en")
        book.add_author("Digest")
        book.add_metadata("DC", "date", today)
        book.add_metadata("DC", "publisher", "odd-jobs")
        book.add_metadata("DC", "subject", "Reading digest")
        book.add_metadata(
            "DC",
            "description",
            f"{post_count} posts from {len(by_source)} feeds: " + ", ".join(sorted(by_source)),
        )
        book.add_item(
            epub.EpubItem(uid="style", file_name="style/digest.css", media_type="text/css", content=STYLE)
        )

        toc: list = []
        spine: list = ["nav"]

        if truncated:
            lines = "".join(
                f"<li>{html.escape(src)} — {n} more not included, will appear in a future digest</li>"
                for src, n in truncated.items()
            )
            note = epub.EpubHtml(title="Note: some feeds were capped", file_name="note.xhtml", lang="en")
            note.content = (
                f'<div class="note"><h1>Some feeds hit the {MAX_PER_FEED}-post cap this run</h1>'
                f"<ul>{lines}</ul></div>"
            )
            note.add_link(href="style/digest.css", rel="stylesheet", type="text/css")
            book.add_item(note)
            toc.append(note)
            spine.append(note)

        i = 0
        for source, source_posts in by_source.items():
            section_title = source
            if source in truncated:
                section_title += f" ({len(source_posts)} of {len(source_posts) + truncated[source]})"
            chapters = []
            for title, link, author, body in source_posts:
                i += 1
                ch = epub.EpubHtml(title=title, file_name=f"post{i}.xhtml", lang="en")
                byline = (
                    f'<p class="byline">{html.escape(author)} — '
                    f'<a href="{html.escape(link)}">{html.escape(link)}</a></p>'
                )
                ch.content = f"<h1>{html.escape(title)}</h1>{byline}{to_xhtml(body)}"
                ch.add_link(href="style/digest.css", rel="stylesheet", type="text/css")
                book.add_item(ch)
                chapters.append(ch)
                spine.append(ch)
            toc.append((epub.Section(section_title), tuple(chapters)))

        book.toc = tuple(toc)
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = spine
        return book
