import os

eval_dir = "data/evaluation"
output_file = "data/image_pdf_ids.txt"

pdf_ids = []

for fname in os.listdir(eval_dir):
    if fname.endswith(".json") and fname.split(".")[0].isdigit():
        pdf_ids.append(fname.split(".")[0])

with open(output_file, "w", encoding="utf-8") as f:
    f.write("\n".join(sorted(pdf_ids)))

print(f"✅ Wrote {len(pdf_ids)} verified image-based PDF IDs to {output_file}")
