import httpx
from bs4 import BeautifulSoup

client = httpx.Client(headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
})
r = client.get("https://diskwaladownloader.flowvideoplayer.com")
soup = BeautifulSoup(r.text, "html.parser")
token_tag = soup.find("meta", {"name": "csrf-token"})
csrf_token = token_tag.get("content") if token_tag else ""
print("CSRF Token:", csrf_token)

post_headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "X-CSRF-TOKEN": csrf_token,
    "Referer": "https://diskwaladownloader.flowvideoplayer.com/",
    "Origin": "https://diskwaladownloader.flowvideoplayer.com"
}
payload = {"url": "https://www.diskwala.com/app/6ac9c34d2a52418b24ee459d"}

r2 = client.post("https://diskwaladownloader.flowvideoplayer.com/searchVideo", headers=post_headers, json=payload)
print("Search status:", r2.status_code)
print("Search response:", r2.text)
