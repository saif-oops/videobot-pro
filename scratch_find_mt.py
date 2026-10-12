import re

js = open("main.js", "r", encoding="utf-8").read()

# Let's search for mt= or function mt or where useParams or /app/ is handled
# Let's search for occurrences of downloadApp or where mt is defined
pos = js.find('downloadApp')
print("downloadApp pos:", pos)
if pos != -1:
    print(js[pos-300:pos+300])

# Look for 'mt='
for m in re.finditer(r'(?:const|let|var|function)\s+mt\s*=', js):
    print("Found mt definition at:", m.start())
    print(js[m.start():m.start()+500])
