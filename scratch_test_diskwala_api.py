import httpx
import json

url = "https://ddudapidd.diskwala.com/api/v1/file/temp_info"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Origin": "https://www.diskwala.com",
    "Referer": "https://www.diskwala.com/",
    "Content-Type": "application/json",
}
data = {"id": "6ac9c34d2a52418b24ee459d"}

try:
    r = httpx.post(url, headers=headers, json=data, timeout=15.0)
    print("Status:", r.status_code)
    print("Headers:", dict(r.headers))
    print("Body:", r.text[:1000])
except Exception as e:
    print("Error:", e)
