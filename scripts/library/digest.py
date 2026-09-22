"""Bundle new posts from feeds.txt into one EPUB and drop it in the CWA ingest folder."""
import datetime
import json
import os
import pathlib

import feedparser
from ebooklib import epub

FEEDS = pathlib.Path("/config/feeds.txt")
STATE = pathlib.Path("/data/seen.json")
OUT = pathlib.Path("/ingest")
MAX_PER_FEED = 20  # cap per feed per run, so the first run isn't a huge backlog

# Matches the PUID/PGID the cwa container runs as (set via DIGEST_PUID/DIGEST_PGID
# in docker-compose.library.yml, defaulting to 1000/1000) so CWA's ingest watcher
# can read and delete the file after import.
OWNER_UID = int(os.environ.get("DIGEST_PUID", "1000"))
OWNER_GID = int(os.environ.get("DIGEST_PGID", "1000"))

seen = set(json.loads(STATE.read_text())) if STATE.exists() else set()
posts = []

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
        # Feeds list entries newest-first; reverse the selected batch so a
        # serialized work (e.g. a book posted chapter by chapter) reads in
        # the right order in the bundled EPUB instead of newest-chapter-first.
        for e in reversed(new[:MAX_PER_FEED]):
            body = e.content[0].value if e.get("content") else e.get("summary", "")
            posts.append((source, e.get("title", "Untitled"), e.get("link", ""), body))
    except Exception as e:
        print(f"Skipping {url}: {e}")
        continue

if not posts:
    print("Nothing new.")
    STATE.write_text(json.dumps(sorted(seen)))
    raise SystemExit

today = datetime.date.today().isoformat()
book = epub.EpubBook()
book.set_identifier(f"digest-{today}")
book.set_title(f"Reading list {today}")
book.set_language("en")
book.add_author("Digest")

chapters = []
for i, (source, title, link, body) in enumerate(posts, 1):
    ch = epub.EpubHtml(title=title, file_name=f"post{i}.xhtml", lang="en")
    ch.content = f"<h1>{title}</h1><p><em>{source}</em></p><p><a href=\"{link}\">{link}</a></p>{body}"
    book.add_item(ch)
    chapters.append(ch)

book.toc = tuple(chapters)
book.add_item(epub.EpubNcx())
book.add_item(epub.EpubNav())
book.spine = ["nav"] + chapters

path = OUT / f"reading-{today}.epub"
epub.write_epub(str(path), book)
os.chown(path, OWNER_UID, OWNER_GID)
STATE.write_text(json.dumps(sorted(seen)))
print(f"Wrote {path} with {len(posts)} posts.")
