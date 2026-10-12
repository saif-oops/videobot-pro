import re

js = open("main.js", "r", encoding="utf-8").read()

pos = js.find('setMagicFile')
print("pos setMagicFile:", pos)
if pos != -1:
    print(js[pos-300:pos+200])
