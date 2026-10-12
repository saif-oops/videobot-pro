from utils.downloader import _extract_terabox_fast

# Test valid link with 1024tera vs terasharelink vs 1024terabox
valid_surl = "1WKZGQQACZjl-eMSKvahxPQ"
test_urls = [
    f"https://1024tera.com/s/{valid_surl}",
    f"https://terabox.com/s/{valid_surl}",
    f"https://teraboxapp.com/s/{valid_surl}",
    f"https://terasharelink.com/s/{valid_surl}",
    f"https://terasharefile.com/s/{valid_surl}",
    f"https://1024terabox.com/s/{valid_surl}",
]

for u in test_urls:
    print(f"\n--- Testing {u} ---")
    try:
        res = _extract_terabox_fast(u)
        print("Success! Title:", res.get("title"))
    except Exception as e:
        print("Failed:", e)
