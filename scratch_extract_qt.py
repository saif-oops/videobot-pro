import re

js = open("main.js", "r", encoding="utf-8").read()
m = re.search(r'const\s+qt\s*=\s*"([^"]+)"', js)
if m:
    qt = m.group(1)
    print("Found qt length:", len(qt))
    open("qt.txt", "w", encoding="utf-8").write(qt)
else:
    print("qt not found")
