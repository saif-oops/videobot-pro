import re

js = open("main.js", "r", encoding="utf-8").read()

matches = re.findall(r'Zt\.(?:post|get)\(["\']([^"\']+)["\']', js)
print("All Zt endpoints:\n", sorted(set(matches)))
