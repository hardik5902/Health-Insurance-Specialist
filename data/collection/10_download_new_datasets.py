"""
Download additional structured datasets not in 01_download_datasets.py.
Sources: CMS QHP Landscape, CMS Medicare Provider Charge Data,
         NHIS (National Health Interview Survey), ACS Health Insurance (Census API).

Run:
    python 10_download_new_datasets.py --all
    python 10_download_new_datasets.py --qhp --nhis
"""

import json
import os
import zipfile
import requests
from pathlib import Path
from typing import Optional

RAW_DIR = Path(__file__).parent.parent / "raw"


def _download_file(url: str, dest: Path, label: str) -> bool:
    if dest.exists():
        print(f"  Already downloaded: {dest.name}")
        return True
    print(f"  Downloading {label} ...")
    try:
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        print(f"\r  {downloaded / total * 100:.1f}%", end="", flush=True)
        print()
        return True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def _extract_zip(zip_path: Path, out_dir: Path, label: str) -> bool:
    if not zip_path.exists():
        print(f"  ERROR: Missing file for extraction: {zip_path}")
        return False
    if not zipfile.is_zipfile(zip_path):
        print(f"  ERROR: {label} is not a valid zip file: {zip_path.name}")
        return False

    print(f"  Extracting to {out_dir} ...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(out_dir)
    print(f"  -> {label} ready at {out_dir}\n")
    return True


# ── CMS QHP Landscape ─────────────────────────────────────────────────────────

QHP_LANDSCAPE_URLS = {
    "2025": "https://download.cms.gov/marketplace-puf/2025/landscape-individual-market-medical.zip",
    "2024": "https://download.cms.gov/marketplace-puf/2024/landscape-individual-market-medical.zip",
}


def download_qhp_landscape(year: str = "2024"):
    """
    QHP Landscape: every marketplace plan with premiums, deductibles,
    metal tier, plan type for all states. Great for plan comparison features.
    """
    url = QHP_LANDSCAPE_URLS.get(year)
    if not url:
        print(f"  No URL configured for year {year}")
        return

    out_dir = RAW_DIR / "cms_qhp_landscape" / year
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"qhp-landscape-{year}.zip"

    if _download_file(url, zip_path, f"CMS QHP Landscape {year}"):
        _extract_zip(zip_path, out_dir, f"CMS QHP Landscape {year}")


# ── CMS Medicare Provider Charge Data ────────────────────────────────────────

MEDICARE_PROVIDER_URLS = {
    "2022": "https://data.cms.gov/sites/default/files/2023-10/Medicare_Provider_Utilization_and_Payment_Data__Physician_and_Other_Practitioners_CY2022.zip",
}


def download_medicare_provider_charges(year: str = "2022"):
    """
    What providers charge Medicare for procedures.
    Teaches the model about price variation — same procedure, different costs
    at different hospitals and providers.
    """
    url = MEDICARE_PROVIDER_URLS.get(year)
    if not url:
        print(f"  No URL configured for year {year}")
        return

    out_dir = RAW_DIR / "cms_provider_charges" / year
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"medicare-provider-charges-{year}.zip"

    if _download_file(url, zip_path, f"CMS Medicare Provider Charges {year}"):
        _extract_zip(zip_path, out_dir, f"CMS Medicare Provider Charges {year}")


# ── NHIS (National Health Interview Survey) ───────────────────────────────────

NHIS_URLS = {
    "2022": "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Datasets/NHIS/2022/adult22csv.zip",
    "2021": "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Datasets/NHIS/2021/adult21csv.zip",
}


def download_nhis(year: str = "2022"):
    """
    National Health Interview Survey: real survey data about how Americans
    experience health coverage — gaps, satisfaction, access to care.
    """
    url = NHIS_URLS.get(year)
    if not url:
        print(f"  No URL configured for year {year}")
        return

    out_dir = RAW_DIR / "nhis" / year
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"nhis-adult-{year}.zip"

    if _download_file(url, zip_path, f"NHIS Adult {year}"):
        print(f"  Extracting ...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(out_dir)
        print(f"  -> NHIS {year} ready at {out_dir}\n")


# ── ACS Health Insurance (Census Bureau API) ──────────────────────────────────

ACS_TABLES = {
    "B27001": "Health Insurance Coverage Status by Sex by Age",
    "B27010": "Types of Health Insurance Coverage by Age",
    "B27020": "Health Insurance Coverage Status by Citizenship",
}


def download_acs_health_insurance(year: int = 2022, api_key: Optional[str] = None):
    """
    American Community Survey health insurance coverage data from Census Bureau.
    State-level and national coverage statistics.

    Get a free API key at: api.census.gov/data/key_signup.html
    Or set env var: CENSUS_API_KEY
    """
    key = api_key or os.environ.get("CENSUS_API_KEY", "")
    out_dir = RAW_DIR / "acs_health_insurance"
    out_dir.mkdir(parents=True, exist_ok=True)

    base_url = f"https://api.census.gov/data/{year}/acs/acs1"

    for table_id, description in ACS_TABLES.items():
        out_file = out_dir / f"{table_id}_{year}.json"
        if out_file.exists():
            print(f"  Already downloaded: {out_file.name}")
            continue

        params = {
            "get": f"group({table_id})",
            "for": "us:1",
        }
        if key:
            params["key"] = key

        print(f"  Fetching ACS table {table_id}: {description} ...")
        try:
            r = requests.get(base_url, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            record = {
                "table": table_id,
                "description": description,
                "year": year,
                "source": "US Census Bureau ACS",
                "data": data,
            }
            out_file.write_text(
                json.dumps(record, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            print(f"  Saved: {out_file.name}")
        except Exception as e:
            print(f"  ERROR fetching {table_id}: {e}")
            if not key:
                print("  TIP: Set CENSUS_API_KEY env var for better rate limits")

    print(f"  -> ACS Health Insurance data ready at {out_dir}\n")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Download additional insurance datasets")
    p.add_argument("--qhp", action="store_true", help="CMS QHP Landscape")
    p.add_argument("--qhp-year", default="2024", help="QHP year (default: 2024)")
    p.add_argument("--provider-charges", action="store_true",
                   help="CMS Medicare Provider Charge Data")
    p.add_argument("--nhis", action="store_true",
                   help="National Health Interview Survey")
    p.add_argument("--nhis-year", default="2022", help="NHIS year (default: 2022)")
    p.add_argument("--acs", action="store_true",
                   help="ACS Health Insurance (Census API)")
    p.add_argument("--acs-year", type=int, default=2022,
                   help="ACS year (default: 2022)")
    p.add_argument("--census-api-key", default=None,
                   help="Census API key (or set CENSUS_API_KEY env var)")
    p.add_argument("--all", action="store_true", help="Download everything")
    args = p.parse_args()

    if args.all or args.qhp:
        download_qhp_landscape(args.qhp_year)
    if args.all or args.provider_charges:
        download_medicare_provider_charges()
    if args.all or args.nhis:
        download_nhis(args.nhis_year)
    if args.all or args.acs:
        download_acs_health_insurance(args.acs_year, args.census_api_key)
