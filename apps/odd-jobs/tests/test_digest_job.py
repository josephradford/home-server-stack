import json
import zipfile
from datetime import time

import httpx
import pytest

from oddjobs.jobs import JobContext
from oddjobs.jobs.digest import DigestJob


def rss(title, items):
    body = "".join(
        f"<item><title>{t}</title><link>{link}</link><guid>{link}</guid>"
        f"<description><![CDATA[{desc}]]></description></item>"
        for t, link, desc in items
    )
    return f'<?xml version="1.0"?><rss version="2.0"><channel><title>{title}</title>{body}</channel></rss>'


def make_ctx(tmp_path, handler, urls=("https://a.example/feed",)):
    feeds = tmp_path / "feeds.txt"
    feeds.write_text("# comment\n\n" + "\n".join(urls) + "\n")
    return JobContext(
        config_path=tmp_path / "calendars.yaml",
        out_dir=tmp_path / "out",
        uid_domain="jobs.example.com",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        feeds_path=feeds,
        ingest_dir=tmp_path / "ingest",
        data_dir=tmp_path / "data",
    )


def serve(feeds):
    def handler(request):
        text = feeds.get(str(request.url))
        if text is None:
            return httpx.Response(500)
        return httpx.Response(200, text=text)

    return handler


def epubs(ctx):
    return sorted(ctx.ingest_dir.glob("*.epub"))


def epub_text(path):
    with zipfile.ZipFile(path) as z:
        return "\n".join(z.read(n).decode("utf-8", "replace") for n in z.namelist())


def test_writes_epub_and_reports_counts(tmp_path):
    feed = rss("Blog A", [("Post 1", "https://a.example/1", "<p>hello</p>")])
    ctx = make_ctx(tmp_path, serve({"https://a.example/feed": feed}))
    result = DigestJob().run(ctx)
    assert result.detail == "1 posts from 1 feeds"
    [path] = epubs(ctx)
    assert "Post 1" in epub_text(path)
    assert not list(ctx.ingest_dir.glob("*.tmp"))


def test_second_run_finds_nothing_new(tmp_path):
    feed = rss("Blog A", [("Post 1", "https://a.example/1", "x")])
    ctx = make_ctx(tmp_path, serve({"https://a.example/feed": feed}))
    DigestJob().run(ctx)
    for p in epubs(ctx):
        p.unlink()
    assert DigestJob().run(ctx).detail == "Nothing new"
    assert epubs(ctx) == []


def test_new_posts_only_after_seen_state(tmp_path):
    feeds = {"https://a.example/feed": rss("Blog A", [("Post 1", "https://a.example/1", "x")])}
    ctx = make_ctx(tmp_path, serve(feeds))
    DigestJob().run(ctx)
    feeds["https://a.example/feed"] = rss(
        "Blog A", [("Post 2", "https://a.example/2", "y"), ("Post 1", "https://a.example/1", "x")]
    )
    assert DigestJob().run(ctx).detail == "1 posts from 1 feeds"
    text = epub_text(epubs(ctx)[-1])
    assert "Post 2" in text


def test_caps_per_feed_and_adds_note(tmp_path):
    items = [(f"Post {i}", f"https://a.example/{i}", "x") for i in range(25)]
    ctx = make_ctx(tmp_path, serve({"https://a.example/feed": rss("Blog A", items)}))
    result = DigestJob().run(ctx)
    assert result.detail == "20 posts from 1 feeds"
    text = epub_text(epubs(ctx)[0])
    assert "5 more not included" in text
    assert "Blog A (20 of 25)" in text


def test_oldest_first_within_a_batch(tmp_path):
    items = [("Newest", "https://a.example/3", "x"), ("Middle", "https://a.example/2", "x"),
             ("Oldest", "https://a.example/1", "x")]
    ctx = make_ctx(tmp_path, serve({"https://a.example/feed": rss("Blog A", items)}))
    DigestJob().run(ctx)
    with zipfile.ZipFile(epubs(ctx)[0]) as z:
        chapters = [z.read(n).decode() for n in sorted(z.namelist()) if n.endswith("post1.xhtml")]
    assert "Oldest" in chapters[0]


def test_bad_feed_does_not_stop_the_others(tmp_path):
    good = rss("Good", [("Ok post", "https://good.example/1", "x")])
    ctx = make_ctx(
        tmp_path,
        serve({"https://good.example/feed": good}),  # bad.example returns 500
        urls=("https://bad.example/feed", "https://good.example/feed"),
    )
    result = DigestJob().run(ctx)
    assert result.detail.startswith("1 posts from 1 feeds")
    assert "1 feed failed" in result.detail
    assert "Ok post" in epub_text(epubs(ctx)[0])


def test_malformed_html_is_coerced_to_valid_xhtml(tmp_path):
    feed = rss("Blog A", [("Post 1", "https://a.example/1", "<p>one<br>two<img src='x.png'>")])
    ctx = make_ctx(tmp_path, serve({"https://a.example/feed": feed}))
    DigestJob().run(ctx)
    with zipfile.ZipFile(epubs(ctx)[0]) as z:
        from lxml import etree

        for n in z.namelist():
            if n.startswith("EPUB/post"):
                etree.fromstring(z.read(n))  # must be well-formed XML


def test_entries_without_id_or_link_are_skipped(tmp_path):
    feed = (
        '<?xml version="1.0"?><rss version="2.0"><channel><title>T</title>'
        "<item><title>No identity</title></item></channel></rss>"
    )
    ctx = make_ctx(tmp_path, serve({"https://a.example/feed": feed}))
    assert DigestJob().run(ctx).detail == "Nothing new"


def test_seen_state_is_persisted_as_json(tmp_path):
    feed = rss("Blog A", [("Post 1", "https://a.example/1", "x")])
    ctx = make_ctx(tmp_path, serve({"https://a.example/feed": feed}))
    DigestJob().run(ctx)
    assert json.loads((ctx.data_dir / "digest-seen.json").read_text()) == ["https://a.example/1"]


def test_job_runs_at_configured_time():
    assert DigestJob(run_at=time(5, 0)).run_at == time(5, 0)
    assert DigestJob().name == "digest"
