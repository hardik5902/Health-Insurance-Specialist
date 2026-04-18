"""
Collect state insurance commissioner consumer guides.
Focuses on the 10 most populous states first, then expands.
Each state's department of insurance publishes consumer guides and rate filings.
"""

import json
import time
import hashlib
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

RAW_DIR = Path(__file__).parent.parent / "raw" / "state_resources"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; HealthInsuranceResearchBot/1.0; "
        "+https://github.com/your-repo)"
    )
}
DELAY = 1.5

# State insurance commissioner / marketplace sites — public domain content
STATE_SOURCES = {
    "california": {
        "seeds": [
            "https://www.insurance.ca.gov/01-consumers/",
            "https://www.coveredca.com/support/",
        ],
        "allowed_prefixes": [
            "https://www.insurance.ca.gov/01-consumers/",
            "https://www.coveredca.com/support/",
        ],
        "max_pages": 100,
    },
    "texas": {
        "seeds": ["https://www.tdi.texas.gov/health/index.html"],
        "allowed_prefixes": ["https://www.tdi.texas.gov/health/"],
        "max_pages": 80,
    },
    "florida": {
        "seeds": ["https://www.myfloridacfo.com/Division/Consumers/"],
        "allowed_prefixes": ["https://www.myfloridacfo.com/Division/Consumers/"],
        "max_pages": 80,
    },
    "new_york": {
        "seeds": [
            "https://www.dfs.ny.gov/consumers/health_insurance",
            "https://nystateofhealth.ny.gov/",
        ],
        "allowed_prefixes": [
            "https://www.dfs.ny.gov/consumers/health_insurance",
            "https://nystateofhealth.ny.gov/",
        ],
        "max_pages": 80,
    },
    "pennsylvania": {
        "seeds": ["https://www.insurance.pa.gov/Consumers/Health/Pages/default.aspx"],
        "allowed_prefixes": ["https://www.insurance.pa.gov/Consumers/"],
        "max_pages": 60,
    },
    "illinois": {
        "seeds": ["https://insurance.illinois.gov/Consumer/Health/"],
        "allowed_prefixes": ["https://insurance.illinois.gov/Consumer/"],
        "max_pages": 60,
    },
    "ohio": {
        "seeds": ["https://insurance.ohio.gov/consumer/health-coverage/"],
        "allowed_prefixes": ["https://insurance.ohio.gov/consumer/"],
        "max_pages": 60,
    },
    "georgia": {
        "seeds": ["https://oci.georgia.gov/consumers"],
        "allowed_prefixes": ["https://oci.georgia.gov/consumers"],
        "max_pages": 60,
    },
    "michigan": {
        "seeds": ["https://www.michigan.gov/difs/consumers/health"],
        "allowed_prefixes": ["https://www.michigan.gov/difs/consumers/health"],
        "max_pages": 60,
    },
    "north_carolina": {
        "seeds": ["https://www.ncdoi.gov/consumers/health-insurance"],
        "allowed_prefixes": ["https://www.ncdoi.gov/consumers/"],
        "max_pages": 60,
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
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def save_page(out_dir: Path, state: str, url: str, text: str) -> None:
    slug = hashlib.md5(url.encode()).hexdigest()[:12]
    record = {"state": state, "url": url, "text": text}
    with open(out_dir / f"{slug}.json", "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)


def crawl_state(state: str, config: dict) -> int:
    out_dir = RAW_DIR / state
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
            save_page(out_dir, state, url, text)
            saved += 1
            print(f"  [{state}][{saved}] {url}")

        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            link = urljoin(url, a["href"])
            clean = urlparse(link)._replace(fragment="", query="").geturl()
            if any(clean.startswith(p) for p in config["allowed_prefixes"]) and clean not in visited:
                queue.append(clean)

        time.sleep(DELAY)

    print(f"  → {state}: {saved} pages saved\n")
    return saved


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Collect state insurance commissioner guides")
    parser.add_argument(
        "--states",
        nargs="+",
        choices=list(STATE_SOURCES) + ["all"],
        default=["all"],
    )
    args = parser.parse_args()

    targets = list(STATE_SOURCES) if "all" in args.states else args.states
    for state in targets:
        crawl_state(state, STATE_SOURCES[state])
