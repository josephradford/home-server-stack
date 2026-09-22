"""Bundle new posts from feeds.txt into one EPUB and drop it in the CWA ingest folder."""
import datetime
import html
import json
import os
import pathlib

import feedparser
from ebooklib import epub
from lxml.etree import tostring
from lxml.html import fromstring

FEEDS = pathlib.Path("/config/feeds.txt")
STATE = pathlib.Path("/data/seen.json")
OUT = pathlib.Path("/ingest")
MAX_PER_FEED = 20  # cap per feed per run, so the first run isn't a huge backlog

# Matches the PUID/PGID the cwa container runs as (set via DIGEST_PUID/DIGEST_PGID
# in docker-compose.library.yml, defaulting to 1000/1000) so CWA's ingest watcher
# can read and delete the file after import.
OWNER_UID = int(os.environ.get("DIGEST_PUID", "1000"))
OWNER_GID = int(os.environ.get("DIGEST_PGID", "1000"))

STYLE = """
body { font-family: serif; line-height: 1.5; margin: 1em; }
h1 { font-size: 1.4em; margin-bottom: 0.1em; }
h2 { font-size: 1.6em; border-bottom: 1px solid #999; padding-bottom: 0.2em; }
.byline { font-style: italic; color: #555; margin-top: 0; }
.byline a { color: #555; }
.note { background: #f4f4f4; border-left: 4px solid #c92a2a; padding: 0.6em 1em; }
"""


def to_xhtml(fragment):
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
    except Exception:
        return f"<p>{html.escape(fragment)}</p>"


seen = set(json.loads(STATE.read_text())) if STATE.exists() else set()
# source -> list of (title, link, author, body)
by_source = {}
# sources where more new posts were available than MAX_PER_FEED allowed
truncated = {}

urls = [
    line.strip()
    for line in FEEDS.read_text().splitlines()
    if line.strip() and not line.strip().startswith("#")
]

for url in urls:
    try:
        feed = feedparser.parse(url)
        source = feed.feed.get("title", url)
        # Entries with neither id nor link have no stable identity for dedup;
        # skip them entirely rather than risk re-bundling them every run or
        # polluting `seen` with None (which would crash sorted() later).
        new = [
            e
            for e in feed.entries
            if (e.get("id") or e.get("link")) and (e.get("id") or e.get("link")) not in seen
        ]
        # Mark everything as seen, but only include the newest few
        for e in feed.entries:
            key = e.get("id") or e.get("link")
            if key:
                seen.add(key)
        if len(new) > MAX_PER_FEED:
            truncated[source] = len(new) - MAX_PER_FEED
            print(f"{source}: {len(new)} new, only taking {MAX_PER_FEED} — {truncated[source]} left for next run")
        # Feeds list entries newest-first; reverse the selected batch so a
        # serialized work (e.g. a book posted chapter by chapter) reads in
        # the right order in the bundled EPUB instead of newest-chapter-first.
        for e in reversed(new[:MAX_PER_FEED]):
            body = e.content[0].value if e.get("content") else e.get("summary", "")
            author = e.get("author", source)
            by_source.setdefault(source, []).append((e.get("title", "Untitled"), e.get("link", ""), author, body))
    except Exception as e:
        print(f"Skipping {url}: {e}")
        continue

if not by_source:
    print("Nothing new.")
    STATE.write_text(json.dumps(sorted(seen)))
    raise SystemExit

today = datetime.date.today().isoformat()
post_count = sum(len(v) for v in by_source.values())

book = epub.EpubBook()
book.set_identifier(f"digest-{today}")
book.set_title(f"Reading list {today}")
book.set_language("en")
book.add_author("Digest")
book.add_metadata("DC", "date", today)
book.add_metadata("DC", "publisher", "library-digest")
book.add_metadata("DC", "subject", "Reading digest")
book.add_metadata(
    "DC",
    "description",
    f"{post_count} posts from {len(by_source)} feeds: " + ", ".join(sorted(by_source)),
)

style = epub.EpubItem(uid="style", file_name="style/digest.css", media_type="text/css", content=STYLE)
book.add_item(style)

toc = []
spine = ["nav"]

if truncated:
    lines = "".join(f"<li>{html.escape(src)} — {n} more not included, will appear in a future digest</li>" for src, n in truncated.items())
    note = epub.EpubHtml(title="Note: some feeds were capped", file_name="note.xhtml", lang="en")
    note.content = f'<div class="note"><h1>Some feeds hit the {MAX_PER_FEED}-post cap this run</h1><ul>{lines}</ul></div>'
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
        byline = f'<p class="byline">{html.escape(author)} — <a href="{html.escape(link)}">{html.escape(link)}</a></p>'
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

path = OUT / f"reading-{today}.epub"
epub.write_epub(str(path), book)
os.chown(path, OWNER_UID, OWNER_GID)
STATE.write_text(json.dumps(sorted(seen)))
print(f"Wrote {path} with {post_count} posts from {len(by_source)} feeds.")
