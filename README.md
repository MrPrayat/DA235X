# DA235X
Master Thesis

Körning av koden i extraction_script.py kräver installation av OpenAI SDK och export av API-nyckel enligt instruktioner här: https://platform.openai.com/docs/libraries?desktop-os=windows&language=python



# 🧾 Extraction Scripts

This folder contains scripts for running PDF extraction of housing inspection reports using GPT-4o.

## Overview

We support two modes:

- `batch_extraction.py` – Process multiple reports from `data/inspection_urls.csv`
- `run_single_extraction.py` – Re-extract a specific PDF by its ID (e.g. for debugging)

All shared logic is located in `extraction_script.py`, but that file is no longer used directly by day-to-day workflows.

---

## 📄 `run_single_extraction.py`

Use this to manually re-extract specific PDFs.

### Example usage

```bash
python -m extraction.run_single_extraction
```

Inside the script, update the list of IDs:

```python
extract_specific_pdfs(["3578724"], csv_path="data/inspection_urls.csv")
```

Replace the array with any PDF IDs you need to reprocess.

---

## 📂 `batch_extraction.py`

Use this to process multiple PDFs in bulk based on inspection report CSV.

### Example usage

```bash
python -m extraction.batch_extraction
```

Inside the script, configure:

```python
run_pdf_tests(
    test_amount=5,        # number of PDFs to run
    skip_existing=True,   # skip already extracted PDFs
)
```

- `test_amount`: how many PDFs to process
- `skip_existing`: if `True`, will skip PDFs with existing output

---

> 🔧 **Tip:** For any shared logic (GPT calls, image preprocessing, normalization), see `utils/helpers.py`.