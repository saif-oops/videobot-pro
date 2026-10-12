import httpx
import re

url = "https://www.diskwala.com/static/js/197.c144ca3c.chunk.js"
r = httpx.get(url)
print("197 chunk status:", r.status_code, "Length:", len(r.text))
js = r.text

# Look for API calls or endpoints or urls in chunk 197
urls = set(re.findall(r'["\'](/[^"\']+|https?://[^"\']+)["\']', js))
for u in sorted(urls):
    if any(k in u for k in ("api", "app", "file", "video", "item", "share", "post", "get")):
        print("Endpoint / URL:", u)

# Let's inspect axios or api calls in chunk 197
# Search for get( or post(
matches = re.findall(r'\.get\([^\)]+\)|\.post\([^\)]+\)', js)
for m in matches[:15]:
    print("Call:", m)
