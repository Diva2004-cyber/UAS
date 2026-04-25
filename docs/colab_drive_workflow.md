# GitHub, Google Drive, and Colab Workflow

This project uses a split-storage workflow:

- **Laptop/local:** keep `evidence_raw/` as master evidence and compute SHA-256 hashes.
- **GitHub:** store code, documentation, config, requirements, and lightweight manifests.
- **Google Drive + Colab:** store working copies, processed datasets, results, figures, and model artifacts.

## What Goes to GitHub

Commit these files:

- `PRD.md`, `README.md`, `ai_agents.md`
- `requirements.txt`
- `configs/`
- `docs/`
- `scripts/`
- `evidence_acquired/hash_manifest.csv`
- `evidence_acquired/metadata_log.csv`
- `.gitkeep` placeholders

Do not commit these heavy or sensitive artifacts:

- `evidence_raw/**`
- `evidence_acquired/copied_files/**`
- `dataset_processed/*.csv`
- generated figures/results/models unless they are intentionally small report assets

## Suggested Google Drive Layout

```text
MyDrive/UAS_AI_Text_Forensics/
|-- evidence_acquired/
|   `-- copied_files/
|-- dataset_processed/
|-- models/
|-- results/
|   |-- tables/
|   |-- figures/
|   `-- suspicious_segments/
`-- repo/
```

## Colab Bootstrap

Run this in Colab:

```python
from google.colab import drive
drive.mount("/content/drive")
```

Clone the GitHub repository:

```bash
cd /content/drive/MyDrive/UAS_AI_Text_Forensics/repo
git clone https://github.com/Diva2004-cyber/UAS.git
cd UAS
pip install -r requirements.txt
```

If the repository already exists:

```bash
cd /content/drive/MyDrive/UAS_AI_Text_Forensics/repo/UAS
git pull
pip install -r requirements.txt
```

## Running the Pipeline in Colab

Use Drive paths for heavy outputs:

```bash
python scripts/text_extraction.py \
  --metadata evidence_acquired/metadata_log.csv \
  --output /content/drive/MyDrive/UAS_AI_Text_Forensics/dataset_processed/extracted_text.csv \
  --failures /content/drive/MyDrive/UAS_AI_Text_Forensics/results/tables/extraction_failures.csv

python scripts/preprocess.py \
  --input /content/drive/MyDrive/UAS_AI_Text_Forensics/dataset_processed/extracted_text.csv \
  --output /content/drive/MyDrive/UAS_AI_Text_Forensics/dataset_processed/preprocessed_text.csv

python scripts/preprocess.py --mode segment \
  --input /content/drive/MyDrive/UAS_AI_Text_Forensics/dataset_processed/preprocessed_text.csv \
  --output /content/drive/MyDrive/UAS_AI_Text_Forensics/dataset_processed/segments.csv \
  --annotations-output /content/drive/MyDrive/UAS_AI_Text_Forensics/dataset_processed/segment_annotations.csv
```

## Forensic Note

`evidence_raw/` remains the local master evidence folder and should not be edited
after acquisition. Colab should work from acquired/working copies and manifests,
not from untracked master evidence.
