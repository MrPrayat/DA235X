import requests
from utils.helpers import get_images_from_pdf

url = "https://documents.bcdn.se/a9/01/5803e049a3c6/.pdf"
pdf_bytes = requests.get(url).content
pages = get_images_from_pdf(pdf_bytes)

print("Pages:", len(pages))
pages[0].show()           # should pop up first page
