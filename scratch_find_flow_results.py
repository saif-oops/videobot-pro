import httpx
from bs4 import BeautifulSoup

r = httpx.get('https://diskwaladownloader.flowvideoplayer.com')
soup = BeautifulSoup(r.text, 'html.parser')
results = soup.find(id='searchResults')
print("searchResults HTML:\n", results.prettify() if results else "Not found")
