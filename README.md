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

Use this to process multiple PDFs in bulk based on your CSV.

### Example usage

```bash
python -m extraction.batch_extraction
```

Inside the script, configure:

```python
run_pdf_tests(
    test_amount=5,        # number of PDFs to run
    skip_existing=True,   # skip already extracted PDFs
    csv_path="data/inspection_urls.csv"
)
```

- `test_amount`: how many PDFs to process
- `skip_existing`: if `True`, will skip PDFs with existing output

---

> 🔧 **Tip:** For any shared logic (GPT calls, image preprocessing, normalization), see `utils/helpers.py`. This keeps the core scripts lean and focused.


---

## 📊 Evaluation & Logging

After running any extraction batch, evaluation metrics are appended to `data/logs/evaluation_log.csv`.

### Quick commands

```bash
# Re‑compute metrics over *all* annotated PDFs and log a new row
python -m evaluation.evaluate_outputs \
       --run_name "<your-note>" \
       --notes    "<what changed>"

# View a rolling summary of recent runs (default 7‑day window)
python -m evaluation.log_summary                # table only
python -m evaluation.log_summary --plot         # table **+** matplotlib plot
```

A typical summary looks like:

```
🕑  Recent runs
2025‑04‑14 14:26  no_appendix            F1  86.7 %  P 86.7 %  R 86.7 %
...
🏆  Best run so far: no_appendix  –  F1 86.7 %
```

All logs live in **`data/logs/`** so they stay version‑controlled with the repo but don’t clutter the main folders.

---

> ℹ️  **Next steps**
>
> * commit‑5 refactor finished – remember to update the root‐level `README.md` if paths change again.
> * feel free to add more CLI flags (e.g. `--today`, `--since <date>`) to `evaluation/log_summary.py` as needed.

