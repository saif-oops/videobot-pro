import subprocess
import re

chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
cmd = [chrome, "--headless=new", "--disable-gpu", "--dump-dom", "https://www.diskwala.com/app/6ac9c34d2a52418b24ee459d"]
p = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
print("Stdout length:", len(p.stdout))
print("Stderr:", p.stderr[:300])

with open("diskwala_dom.html", "w", encoding="utf-8") as f:
    f.write(p.stdout)

# Check what elements are in diskwala_dom.html
print("Matches for video/src/mp4/etc:")
print(re.findall(r'https?://[^\s"\'<>]+\.(?:mp4|m3u8)[^\s"\'<>]*', p.stdout))
print("Titles found:", re.findall(r'<h[1-6][^>]*>([^<]+)</h[1-6]>', p.stdout))
print("Buttons found:", re.findall(r'<button[^>]*>([^<]+)</button>', p.stdout))
