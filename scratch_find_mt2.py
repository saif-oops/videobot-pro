import re

js = open("main.js", "r", encoding="utf-8").read()

# Let's search for mt=
pos = js.find('element:(0,He.jsx)(mt,')
if pos != -1:
    print("Found element:(0,He.jsx)(mt, at", pos)
    print(js[pos-100:pos+100])

# Let's find definition of mt
matches = [m.start() for m in re.finditer(r'\bmt\s*=', js)]
print("mt= positions:", matches)
for p in matches:
    print("Snippet at", p, ":", js[p:p+300])
