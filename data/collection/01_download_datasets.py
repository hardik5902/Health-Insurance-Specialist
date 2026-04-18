"""
Day 1-2: Download structured datasets — InsuranceQA (HuggingFace) and CMS Benefits PUF.
"""

import os
import json
import requests
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

RAW_DIR = Path(__file__).parent.parent / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)


# ── InsuranceQA from HuggingFace ──────────────────────────────────────────────

INSURANCEQA_CANDIDATES = [
    {
        "dataset_id": "recoai/insurance-qa-english",
        "label": "InsuranceQA English",
        "question_keys": ["question", "query", "input", "question_en"],
        "answer_keys": ["answer", "output", "response", "answer_en"],
    },
    {
        "dataset_id": "deccan-ai/insuranceQA-v2",
        "label": "InsuranceQA v2",
        "question_keys": ["input", "question", "question_en"],
        "answer_keys": ["output", "answer", "answer_en", "response"],
    },
    {
        "dataset_id": "rvpierre/insurance-qa-en",
        "label": "Insurance QA EN",
        "question_keys": ["question_en", "question", "input"],
        "answer_keys": ["answer_en", "answer", "output", "response"],
    },
]


def _pick_first(row: Dict, keys: List[str]) -> Optional[str]:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _normalize_records(records: List[Dict], candidate: Dict, split: str) -> List[Dict]:
    normalized = []
    for idx, row in enumerate(records):
        question = _pick_first(row, candidate["question_keys"])
        answer = _pick_first(row, candidate["answer_keys"])
        if not question or not answer:
            continue

        normalized.append(
            {
                "id": row.get("id", f"{split}-{idx}"),
                "split": split,
                "source_dataset": candidate["dataset_id"],
                "source_metadata": {
                    "dataset_id": candidate["dataset_id"],
                    "dataset_label": candidate["label"],
                    "split": split,
                },
                "question": question,
                "answer": answer,
                "topic": row.get("topic") or row.get("topic_en"),
                "source_record": row,
            }
        )
    return normalized

def download_insuranceqa():
    """Download the InsuranceQA dataset (~16k Q&A pairs) from HuggingFace datasets."""
    try:
        from datasets import load_dataset
    except ImportError:
        raise ImportError("Run: pip install datasets")

    print("Downloading InsuranceQA dataset from HuggingFace...")

    ds = None
    selected_candidate = None
    errors = []

    for candidate in INSURANCEQA_CANDIDATES:
        dataset_id = candidate["dataset_id"]
        try:
            print(f"  Trying {dataset_id} ...")
            ds = load_dataset(dataset_id)
            selected_candidate = candidate
            print(f"  Using {dataset_id}")
            break
        except Exception as exc:
            errors.append(f"{dataset_id}: {exc}")
            print(f"  Skipped {dataset_id} ({exc})")

    if ds is None or selected_candidate is None:
        error_text = "\n".join(errors)
        raise RuntimeError(
            "Unable to download an InsuranceQA-style dataset from HuggingFace.\n"
            "Tried these dataset IDs:\n"
            f"{error_text}"
        )

    out_path = RAW_DIR / "insuranceqa"
    out_path.mkdir(exist_ok=True)

    metadata_file = out_path / "source_metadata.json"
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "selected_dataset": selected_candidate["dataset_id"],
                "label": selected_candidate["label"],
                "splits": list(ds.keys()),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    for split in ds:
        records = [dict(row) for row in ds[split]]
        normalized_records = _normalize_records(records, selected_candidate, split)

        raw_file = out_path / f"{split}.raw.json"
        with open(raw_file, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

        normalized_file = out_path / f"{split}.json"
        with open(normalized_file, "w", encoding="utf-8") as f:
            json.dump(normalized_records, f, ensure_ascii=False, indent=2)

        print(
            f"  Saved {len(normalized_records):,} normalized {split} examples "
            f"and {len(records):,} raw rows → {normalized_file}"
        )

    print(f"InsuranceQA download complete.\n")
    return out_path


# ── CMS Benefits and Cost Sharing Public Use File ─────────────────────────────

CMS_PUF_URLS = {
    "2024": "https://download.cms.gov/marketplace-puf/2024/benefits-and-cost-sharing-puf.zip",
    "2023": "https://download.cms.gov/marketplace-puf/2023/benefits-and-cost-sharing-puf.zip",
}


def download_cms_puf(year: str = "2024"):
    url = CMS_PUF_URLS.get(year)
    if not url:
        raise ValueError(f"No URL configured for year {year}.")

    out_dir = RAW_DIR / "cms_puf" / year
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / "benefits-and-cost-sharing-puf.zip"

    if zip_path.exists():
        print(f"CMS PUF {year} already downloaded, skipping.")
    else:
        print(f"Downloading CMS Benefits PUF {year} from {url} ...")
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(zip_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded / total * 100
                        print(f"\r  {pct:.1f}%", end="", flush=True)
        print()

    print(f"Extracting CMS PUF {year}...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(out_dir)
    print(f"  Extracted to {out_dir}\n")
    return out_dir


# ── US Health Insurance Dataset (Kaggle) ──────────────────────────────────────

def download_kaggle_dataset():
    """
    Download the US Health Insurance dataset from Kaggle.
    Requires KAGGLE_USERNAME and KAGGLE_KEY env vars (from ~/.kaggle/kaggle.json).
    """
    try:
        import kaggle  # noqa: F401
    except ImportError:
        raise ImportError("Run: pip install kaggle  and set KAGGLE_USERNAME / KAGGLE_KEY env vars")

    out_dir = RAW_DIR / "kaggle_insurance"
    out_dir.mkdir(exist_ok=True)
    print("Downloading Kaggle US Health Insurance dataset...")
    os.system(
        f'kaggle datasets download -d teertha/ushealthinsurancedataset -p "{out_dir}" --unzip'
    )
    print(f"  Saved to {out_dir}\n")
    return out_dir


# ── MEPS (Medical Expenditure Panel Survey) ───────────────────────────────────

MEPS_HC_URL = (
    "https://meps.ahrq.gov/mepsweb/data_files/pufs/h243/h243csv.zip"  # 2022 full-year
)


def download_meps():
    out_dir = RAW_DIR / "meps"
    out_dir.mkdir(exist_ok=True)
    zip_path = out_dir / "meps_h243.zip"

    if zip_path.exists():
        print("MEPS file already downloaded, skipping.")
    else:
        print(f"Downloading MEPS full-year consolidated file...")
        with requests.get(MEPS_HC_URL, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(zip_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
        print(f"  Saved to {zip_path}")

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(out_dir)
    print(f"  Extracted MEPS to {out_dir}\n")
    return out_dir


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Download structured insurance datasets")
    parser.add_argument("--insuranceqa", action="store_true", help="Download InsuranceQA")
    parser.add_argument("--cms", action="store_true", help="Download CMS Benefits PUF")
    parser.add_argument("--cms-year", default="2024", help="CMS PUF year (default: 2024)")
    parser.add_argument("--kaggle", action="store_true", help="Download Kaggle dataset")
    parser.add_argument("--meps", action="store_true", help="Download MEPS dataset")
    parser.add_argument("--all", action="store_true", help="Download everything")
    args = parser.parse_args()

    if args.all or args.insuranceqa:
        download_insuranceqa()
    if args.all or args.cms:
        download_cms_puf(args.cms_year)
    if args.all or args.kaggle:
        download_kaggle_dataset()
    if args.all or args.meps:
        download_meps()
