import re
import httpx

html = open('scratch_diskwala.html', 'r', encoding='utf-8').read()
scripts = re.findall(r'src=["\']([^"\']+\.js[^"\']*)["\']', html)
print("Found scripts:", scripts)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://www.diskwala.com/app/6ac9c34d2a52418b24ee459d"
}

with httpx.Client(headers=headers, follow_redirects=True) as client:
    for s in scripts:
        url = s if s.startswith("http") else f"https://www.diskwala.com{s}"
        print(f"Fetching {url}...")
        try:
            r = client.get(url)
            content = r.text
            # Look for api endpoints or endpoints containing 6ac9c34d2a52418b24ee459d or 'api'
            apis = set(re.findall(r'["\'](/api/[^"\']+|https?://[^"\']*/api/[^"\']+)["\']', content))
            print("Found APIs in script:", apis)
            keywords = set(re.findall(r'["\']([^"\']*(?:stream|download|file|video|play)[^"\']*)["\']', content))
            print("Keywords (sample):", list(keywords)[:10])
        except Exception as e:
            print("Error:", e)
