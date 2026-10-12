import re

js = open("main.js", "r", encoding="utf-8").read()
matches = re.findall(r'.{0,50}Wt\s*=[^;]+.{0,50}', js)
for m in matches:
    print("Match Wt:", m)
