import httpx

USER_AGENT = "odd-jobs/1.0 (personal calendar sync; once-daily polling)"


def make_client() -> httpx.Client:
    return httpx.Client(
        transport=httpx.HTTPTransport(retries=1),
        timeout=30,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    )
