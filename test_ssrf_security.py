"""Automated test suite verifying SSRF defense on api_stream, api_download, and api_fetch."""
from starlette.testclient import TestClient
from bot import create_starlette_app, is_safe_proxy_url

def test_is_safe_proxy_url():
    # SSRF attack vectors
    blocked_cases = [
        ("http://127.0.0.1:8080/", "Only HTTPS"),
        ("http://169.254.169.254/latest/meta-data/", "Only HTTPS"),
        ("http://localhost/", "Only HTTPS"),
        ("https://127.0.0.1/", "Domain '127.0.0.1' is not allowed"),
        ("https://localhost:8080/", "Disallowed port: 8080"),
        ("https://google.com/", "Domain 'google.com' is not allowed"),
        ("https://evil.terabox.com.attacker.com/", "Domain 'evil.terabox.com.attacker.com' is not allowed"),
        ("file:///etc/passwd", "Only HTTPS"),
        ("https://admin:secret@1024tera.com/", "Userinfo in URL is not allowed"),
        ("gopher://127.0.0.1:6379/", "Only HTTPS"),
    ]
    for url, reason_substr in blocked_cases:
        safe, reason = is_safe_proxy_url(url)
        assert not safe, f"Expected {url} to be blocked, but was allowed"
        assert reason_substr.lower() in reason.lower(), f"Expected '{reason_substr}' in '{reason}'"

    # Legitimate CDN URLs
    allowed_cases = [
        "https://dl-worker.teraboxdl.site?token=123",
        "https://api.teraboxdl.site/get_m3u8_stream_fast?token=abc",
        "https://d.terabox.com/file.mp4",
        "https://1024tera.com/stream/video.m3u8",
    ]
    for url in allowed_cases:
        safe, reason = is_safe_proxy_url(url)
        assert safe, f"Expected {url} to be allowed, but blocked with: {reason}"

async def run_asgi_tests():
    import httpx
    app = create_starlette_app(webhook_mode=False)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Internal loopback attack on /api/stream
        res = await client.get("/api/stream?url=http://127.0.0.1:8080/")
        assert res.status_code == 403, f"Expected 403, got {res.status_code}: {res.text}"
        assert "Forbidden" in res.text

        # 2. Cloud metadata attack on /api/stream
        res = await client.get("/api/stream?url=http://169.254.169.254/latest/meta-data/")
        assert res.status_code == 403, f"Expected 403, got {res.status_code}: {res.text}"
        assert "Forbidden" in res.text

        # 3. External arbitrary host attack on /api/stream
        res = await client.get("/api/stream?url=https://attacker.example.com/malware.exe")
        assert res.status_code == 403, f"Expected 403, got {res.status_code}: {res.text}"
        assert "Forbidden" in res.text

        # 4. Loopback attack on /api/download
        res = await client.get("/api/download?url=http://127.0.0.1:8080/&title=test")
        assert res.status_code == 403, f"Expected 403, got {res.status_code}: {res.text}"
        assert "Forbidden" in res.text

        # 5. Non-whitelisted domain on /api/download
        res = await client.get("/api/download?url=https://google.com/test.mp4&title=test")
        assert res.status_code == 403, f"Expected 403, got {res.status_code}: {res.text}"
        assert "Forbidden" in res.text

        # 6. Arbitrary domain on /api/fetch
        res = await client.post("/api/fetch", json={"url": "http://169.254.169.254/latest"})
        assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
        assert "Only TeraBox and DiskWala" in res.text

        print("PASS: run_asgi_tests (all HTTP endpoints blocked SSRF successfully)")

if __name__ == "__main__":
    import asyncio
    test_is_safe_proxy_url()
    print("PASS: test_is_safe_proxy_url")
    asyncio.run(run_asgi_tests())
    print("\nALL SSRF SECURITY TESTS PASSED SUCCESSFULLY!")

