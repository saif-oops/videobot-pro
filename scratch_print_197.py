js = open("scratch_chunk197.txt", "w", encoding="utf-8")
import httpx
r = httpx.get("https://www.diskwala.com/static/js/197.c144ca3c.chunk.js")
js.write(r.text)
js.close()
print("Entire chunk 197:\n", r.text)
