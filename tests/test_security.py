import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot import create_starlette_app, is_safe_proxy_url

def test_is_safe_proxy_url():
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
        # Loopback attack on /api/stream
        res = await client.get("/api/stream?url=http://127.0.0.1:8080/")
        assert res.status_code == 403

        # Cloud metadata attack on /api/stream
        res = await client.get("/api/stream?url=http://169.254.169.254/latest/meta-data/")
        assert res.status_code == 403

        # External arbitrary host attack on /api/stream
        res = await client.get("/api/stream?url=https://attacker.example.com/malware.exe")
        assert res.status_code == 403

        # Non-whitelisted domain on /api/download
        res = await client.get("/api/download?url=https://google.com/test.mp4&title=test")
        assert res.status_code == 403

        # Arbitrary domain on /api/fetch
        res = await client.post("/api/fetch", json={"url": "http://169.254.169.254/latest"})
        assert res.status_code == 400

if __name__ == "__main__":
    test_is_safe_proxy_url()
    asyncio.run(run_asgi_tests())
    print("ALL SSRF SECURITY TESTS PASSED SUCCESSFULLY!")
