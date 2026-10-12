import re

content = open("main.js", "w", encoding="utf-8")
import httpx
r = httpx.get("https://www.diskwala.com/static/js/main.f1ff7a1b.js")
content.write(r.text)
content.close()

js = r.text
print("JS Length:", len(js))

# Search for matches around 'api/v1'
matches = re.findall(r'.{0,100}api/v1.{0,100}', js)
for m in matches[:10]:
    print("Match:", m)

# Search for matches around '/app/'
matches_app = re.findall(r'.{0,100}/app/.{0,100}', js)
for m in matches_app[:5]:
    print("Match app:", m)
