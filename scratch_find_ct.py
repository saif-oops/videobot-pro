import re

js = open("main.js", "r", encoding="utf-8").read()

pos = js.find('ct=q(')
if pos == -1:
    pos = js.find('ct=')
print("pos ct:", pos)
if pos != -1:
    print(js[pos-50:pos+300])
