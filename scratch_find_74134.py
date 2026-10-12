import re

js = open("main.js", "r", encoding="utf-8").read()
pos = js.find('74134:')
if pos == -1:
    pos = js.find('74134(')
print("pos 74134:", pos)
if pos != -1:
    print(js[pos-50:pos+800])
