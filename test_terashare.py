from utils.downloader import _extract_terabox_fast

url = "https://terasharelink.com/s/11o8o1u7bjkyjveqx_ib_nw"
print("Testing:", url)
try:
    res = _extract_terabox_fast(url)
    print("Success:", res.get("title"))
    print("Stream:", res.get("direct_url")[:100] if res.get("direct_url") else None)
except Exception as e:
    print("Error:", e)

url2 = "https://terasharefile.com/s/11o8o1u7bjkyjveqx_ib_nw"
print("Testing:", url2)
try:
    res2 = _extract_terabox_fast(url2)
    print("Success:", res2.get("title"))
    print("Stream:", res2.get("direct_url")[:100] if res2.get("direct_url") else None)
except Exception as e:
    print("Error:", e)
