import re

js = open("main.js", "r", encoding="utf-8").read()

# Search for 15356: or 15356(
pos = js.find('15356(')
if pos == -1:
    pos = js.find('15356:')
print("pos 15356:", pos)
if pos != -1:
    print(js[pos-50:pos+1000])

# Search for JR: or JR=
pos2 = js.find('JR:')
if pos2 != -1:
    print("pos2 JR:", js[pos2-100:pos2+300])
