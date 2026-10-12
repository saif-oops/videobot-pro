content = open('flow_app.js', 'r', encoding='utf-8').read()
import re

matches = re.findall(r'.{0,100}(?:fetch|http|download|stream|process|extract|api).{0,100}', content)
for m in matches[:20]:
    print("Match:", m)
