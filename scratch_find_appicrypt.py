import re

js = open("main.js", "r", encoding="utf-8").read()

pos = js.find('Appicrypt')
print("Appicrypt pos:", pos)
if pos != -1:
    print(js[pos-200:pos+300])

# Search for getCryptogram
pos2 = js.find('getCryptogram')
print("getCryptogram pos:", pos2)
if pos2 != -1:
    print(js[pos2-200:pos2+300])
