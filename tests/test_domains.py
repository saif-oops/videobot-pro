import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.downloader import normalize_terabox_url, extract_url, detect_platform

def test_terabox_domain_recognition():
    urls = [
        "https://1024tera.com/s/1WKZGQQACZjl-eMSKvahxPQ",
        "https://terabox.com/s/1WKZGQQACZjl-eMSKvahxPQ",
        "https://teraboxapp.com/s/1WKZGQQACZjl-eMSKvahxPQ",
        "https://terasharelink.com/s/1WKZGQQACZjl-eMSKvahxPQ",
        "https://teraboxlinke.com/al/10bqo0dTcy3dodnPedJNpTw",
    ]
    for u in urls:
        assert detect_platform(u) == "terabox", f"Expected {u} to be recognized as TeraBox"

def test_url_normalization():
    # TeraShortner /al/ path
    norm = normalize_terabox_url("https://teraboxlinke.com/al/10bqo0dTcy3dodnPedJNpTw")
    assert "1024tera.com/s/10bqo0dTcy3dodnPedJNpTw" in norm

    # surl query parameter
    norm2 = normalize_terabox_url("https://terasharelink.com/sharing/link?surl=10bqo0dTcy3dodnPedJNpTw")
    assert "1024tera.com/s/10bqo0dTcy3dodnPedJNpTw" in norm2

def test_extraction_code_parsing():
    msg = "Here is the video https://1024tera.com/s/1abc Extraction code: 4xyz"
    url = extract_url(msg)
    assert url == "https://1024tera.com/s/1abc?pwd=4xyz"

if __name__ == "__main__":
    test_terabox_domain_recognition()
    test_url_normalization()
    test_extraction_code_parsing()
    print("ALL DOMAIN TESTS PASSED SUCCESSFULLY!")
