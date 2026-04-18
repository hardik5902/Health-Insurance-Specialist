"""
Scrape nonprofit and advocacy organization insurance guides.
Sources: KFF, Patient Advocate Foundation, HealthInsurance.org,
         Verywell Health, NeedyMeds.
"""

import json
import time
import hashlib
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

RAW_DIR = Path(__file__).parent.parent / "raw" / "advocacy"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; HealthInsuranceResearchBot/1.0; "
        "+https://github.com/your-repo)"
    )
}
DELAY = 1.5

SOURCES = {
    "kff": {
        "seeds": [
            "https://kff.org/health-topics/",
            "https://kff.org/private-insurance/",
            "https://kff.org/medicare/",
            "https://kff.org/medicaid/",
            "https://kff.org/health-reform/",
        ],
        "allowed_prefix": "https://kff.org/",
        "max_pages": 300,
    },
    "healthinsurance_org": {
        "seeds": [
            "https://www.healthinsurance.org/learn/",
            "https://www.healthinsurance.org/obamacare/",
            "https://www.healthinsurance.org/glossary/",
        ],
        "allowed_prefix": "https://www.healthinsurance.org/",
        "max_pages": 200,
    },
    "patient_advocate": {
        "seeds": [
            "https://www.patientadvocate.org/explore-our-resources/",
        ],
        "allowed_prefix": "https://www.patientadvocate.org/",
        "max_pages": 100,
    },
    "verywell_health": {
        "seeds": [
            "https://www.verywellhealth.com/health-insurance-4014797",
        ],
        "allowed_prefix": "https://www.verywellhealth.com/health-insurance",
        "max_pages": 200,
    },
    "needymeds": {
        "seeds": [
            "https://www.needymeds.org/insurance-tips",
            "https://www.needymeds.org/insurance",
        ],
        "allowed_prefix": "https://www.needymeds.org/",
        "max_pages": 100,
    },
}


def fetch(url: str, session: requests.Session):
    try:
        r = session.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"  WARN: {url} → {e}")
        return None


def extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def save_page(out_dir: Path, source: str, url: str, text: str) -> None:
    slug = hashlib.md5(url.encode()).hexdigest()[:12]
    record = {"source": source, "url": url, "text": text}
    with open(out_dir / f"{slug}.json", "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)


def crawl_source(name: str, config: dict) -> int:
    out_dir = RAW_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    visited: set[str] = set()
    queue = list(config["seeds"])
    saved = 0

    while queue and saved < config["max_pages"]:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)

        resp = fetch(url, session)
        if not resp:
            continue

        text = extract_text(resp.text)
        if len(text) > 300:
            save_page(out_dir, name, url, text)
            saved += 1
            print(f"  [{name}][{saved}] {url}")

        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            link = urljoin(url, a["href"])
            clean = urlparse(link)._replace(fragment="", query="").geturl()
            if clean.startswith(config["allowed_prefix"]) and clean not in visited:
                queue.append(clean)

        time.sleep(DELAY)

    print(f"  → {name}: {saved} pages saved\n")
    return saved


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scrape advocacy org insurance content")
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=list(SOURCES) + ["all"],
        default=["all"],
    )
    args = parser.parse_args()

    targets = list(SOURCES) if "all" in args.sources else args.sources
    for name in targets:
        crawl_source(name, SOURCES[name])
