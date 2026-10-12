import re

js = open("main.js", "r", encoding="utf-8").read()
routes = re.findall(r'path:\s*["\']([^"\']+)["\']', js)
print("All React routes:\n", sorted(set(routes)))
