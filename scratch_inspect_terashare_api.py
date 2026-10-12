import httpx
import hashlib
import time

url = "https://terasharelink.com/s/11o8o1u7bjkyjveqx_ib_nw"
t = int(time.time())
secret = f"T9do@SM1?xGn5{t}/api/stream.php"
token = hashlib.md5(secret.encode()).hexdigest()
api_url = f"https://playterabox.com/api/fetch-video?token={token}&t={t}"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Referer": "https://playterabox.com/tools/terabox-online-player",
    "Origin": "https://playterabox.com",
}
payload = {"url": url}

with httpx.Client(headers=headers, timeout=15.0) as client:
    r = client.post(api_url, json=payload)
    print("Status:", r.status_code)
    print("Response JSON:", r.text)

# Also test resolving the redirect of https://terasharelink.com/s/11o8o1u7bjkyjveqx_ib_nw!
print("\nChecking redirects of original URL:")
with httpx.Client(headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}, follow_redirects=True) as client:
    try:
        r2 = client.get(url)
        print("Final URL:", r2.url)
        print("Status:", r2.status_code)
    except Exception as e:
        print("Redirect error:", e)
