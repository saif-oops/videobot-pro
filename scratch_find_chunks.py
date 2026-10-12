import re

js = open("main.js", "r", encoding="utf-8").read()

# Webpack chunk filename function
pos = js.find('static/js/')
print("static/js/ pos:", pos)
if pos != -1:
    print(js[pos-100:pos+200])

# Search for n.u = or chunkId + "."
m = re.search(r'n\.u\s*=\s*function\(e\)\{return\s*([^}]+)\}', js)
if m:
    print("Chunk filename func:", m.group(1))
