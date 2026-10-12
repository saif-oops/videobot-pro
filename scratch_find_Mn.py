import re

js = open("main.js", "r", encoding="utf-8").read()

# Let's search for Mn= or function Mn
pos = js.find('Mn=')
print("pos Mn=:", pos)
if pos != -1:
    print(js[pos-50:pos+500])
