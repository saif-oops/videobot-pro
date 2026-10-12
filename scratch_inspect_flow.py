import httpx
import re

r = httpx.get('https://diskwaladownloader.flowvideoplayer.com')
html = r.text
print("HTML length:", len(html))

# Look for fetch or api or post in the page
scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
for s in scripts:
    if "api" in s or "fetch" in s or "diskwala" in s:
        print("Script snippet:\n", s[:1000])

external_scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html)
print("External scripts:", external_scripts)
