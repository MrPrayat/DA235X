import json
import time
import sys
from pathlib import Path
import requests
from openai import OpenAI


def load_flagged_ids(flagged_file: Path) -> set[str]:
    if not flagged_file.exists():
        print(f"Error: flagged IDs file not found at {flagged_file}")
        sys.exit(1)
    return set(line.strip() for line in flagged_file.read_text().splitlines() if line.strip())


def load_inspection_urls(csv_file: Path) -> 'pd.DataFrame':
    try:
        import pandas as pd
    except ImportError:
        print("pandas is required to read the CSV. Please install with `pip install pandas`.")
        sys.exit(1)
    if not csv_file.exists():
        print(f"Error: CSV file not found at {csv_file}")
        sys.exit(1)
    return pd.read_csv(csv_file, dtype={"id": str, "url": str})


def download_pdf(pdf_id: str, url: str, download_dir: Path) -> Path:
    download_dir.mkdir(parents=True, exist_ok=True)
    local_path = download_dir / f"{pdf_id}.pdf"
    if not local_path.exists():
        print(f"Downloading {pdf_id}...")
        resp = requests.get(url)
        resp.raise_for_status()
        local_path.write_bytes(resp.content)
    else:
        print(f"Already downloaded: {pdf_id}")
    return local_path


def upload_pdf(client: OpenAI, pdf_id: str, local_path: Path, cache: dict, cache_file: Path) -> str:
    if pdf_id in cache:
        return cache[pdf_id]
    for attempt in range(5):
        try:
            print(f"Uploading {pdf_id}...")
            with open(local_path, "rb") as f:
                upload = client.files.create(
                    file=f,
                    purpose="user_data"
                )
            file_id = upload.id
            cache[pdf_id] = file_id
            cache_file.write_text(json.dumps(cache, indent=2))
            return file_id
        except Exception as e:
            wait = 2 ** attempt
            print(f"Upload failed (attempt {attempt+1}): {e}. Retrying in {wait}s...")
            time.sleep(wait)
    print(f"Failed to upload {pdf_id} after retries.")
    sys.exit(1)


def main():
    # Paths
    base_dir = Path(__file__).parent
    project_root = base_dir.parent
    csv_file = project_root / "data" /"inspection_urls.csv"
    # Adjusted flagged file location
    flagged_file = project_root / "data" / "image_pdf_ids.txt"
    download_dir = project_root / "data" / "raw_pdfs"
    cache_file = project_root / "data" / "file_id_cache.json"

    flagged_ids = load_flagged_ids(flagged_file)
    df = load_inspection_urls(csv_file)

    client = OpenAI()

    cache_file.parent.mkdir(parents=True, exist_ok=True)
    if cache_file.exists():
        cache = json.loads(cache_file.read_text())
    else:
        cache = {}

    for _, row in df[df['id'].isin(flagged_ids)].iterrows():
        pdf_id = row['id']
        url = row['url']
        local_path = download_pdf(pdf_id, url, download_dir)
        file_id = upload_pdf(client, pdf_id, local_path, cache, cache_file)
        print(f"Cached {pdf_id} -> {file_id}\n")


if __name__ == "__main__":
    main()