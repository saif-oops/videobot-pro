import re

js = open("main.js", "r", encoding="utf-8").read()

pos = js.find('path:"/c/:code"')
if pos != -1:
    print(js[pos-100:pos+200])
