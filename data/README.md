# Data Collection

## Quick Start

```bash
cd data/collection
pip install -r requirements.txt
python run_all.py                        # Run everything
python run_all.py --steps datasets government   # Run specific steps
```

## Steps and Expected Output

| Script | Step | Expected records | Runtime |
|---|---|---|---|
| `01_download_datasets.py` | InsuranceQA + CMS PUF + MEPS | ~16k + millions of rows | 5–30 min |
| `02_scrape_government_sites.py` | healthcare.gov, medicare.gov, medicaid.gov, DOL, IRS | ~1,150 pages | 30–60 min |
| `03_scrape_insurance_companies.py` | 6 major insurers | ~1,000 pages | 30–60 min |
| `05_scrape_advocacy_orgs.py` | KFF, PAF, Verywell, etc. | ~900 pages | 20–40 min |
| `06_collect_state_resources.py` | 10 state insurance depts | ~680 pages | 20–40 min |

## Setup Required for Kaggle

1. Download `kaggle.json` from your Kaggle account settings
2. Place at `~/.kaggle/kaggle.json`  or set `KAGGLE_USERNAME` and `KAGGLE_KEY` env vars

## Raw Output Structure

```
data/raw/
├── insuranceqa/          ← train.json, test.json, validation.json
├── cms_puf/2024/         ← extracted CSV files
├── meps/                 ← MEPS consolidated CSV
├── healthcare_gov/       ← one JSON per page scraped
├── medicare_gov/
├── medicaid_gov/
├── dol_ebsa/
├── irs/
├── insurance_companies/
│   ├── unitedhealth/
│   ├── cigna/
│   └── ...
├── advocacy/
│   ├── kff/
│   └── ...
└── state_resources/
    ├── california/
    └── ...
```

Next step: run `data/processing/` scripts to convert raw data into instruction-response training pairs.
