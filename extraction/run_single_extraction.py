import os
from extraction.extraction_script import extract_specific_pdfs

def main():
    inspection_urls_path = os.path.join("data", "inspection_urls.csv")
    pdf_ids_to_extract = ["3578724"]  # 🔁 Change this list as needed
    extract_specific_pdfs(pdf_ids_to_extract, inspection_urls_path)

if __name__ == "__main__":
    print("🔁 Running single extraction...")
    main()
