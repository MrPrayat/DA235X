import os
from extraction.extraction_script import run_pdf_tests

def main():
    inspection_urls_path = os.path.join("data", "inspection_urls.csv")
    test_amount = 3
    skip_existing = True

    run_pdf_tests(test_amount, skip_existing, inspection_urls_path)

if __name__ == "__main__":
    print("📦 Running batch extraction...")
    main()
