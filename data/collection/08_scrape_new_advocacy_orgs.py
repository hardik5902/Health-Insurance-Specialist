"""
Scrape additional advocacy/nonprofit organizations not in 05_scrape_advocacy_orgs.py.
Sources: NAIC, Georgetown Health Policy, Families USA, Medicare Rights Center,
         CBPP, Mental Health America, American Cancer Society (insurance section),
         PAN Foundation.

Run:
    python 08_scrape_new_advocacy_orgs.py --all
    python 08_scrape_new_advocacy_orgs.py --sources naic medicare_rights
"""

import hashlib
import json
import re
import time
import random
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

RAW_DIR = Path(__file__).parent.parent / "raw" / "advocacy_additional"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; HealthInsuranceResearchBot/1.0; "
        "Academic/non-commercial research)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
DELAY = 2.0

INSURANCE_KEYWORDS = {
    "deductible", "premium", "copay", "coinsurance", "out-of-pocket",
    "eob", "prior authorization", "denial", "appeal", "claim",
    "in-network", "out-of-network", "formulary", "hsa", "fsa",
    "hmo", "ppo", "hdhp", "aca", "marketplace", "medicare", "medicaid",
    "chip", "cobra", "open enrollment", "special enrollment",
    "coverage", "health insurance", "health plan", "insurer",
    "premium tax credit", "cost sharing", "essential health benefits",
    "surprise billing", "medigap", "medicare advantage",
    "enrollment period", "qualifying life event", "benefit year",
    "out of pocket maximum", "network", "insurance company",
    "insurance denial", "insurance appeal", "parity", "mental health coverage",
}


def make_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3, backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    session.mount("http://", HTTPAdapter(max_retries=retry))
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def fetch(url: str, session: requests.Session):
    try:
        r = session.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"  WARN: {url} -> {e}")
        return None


def extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    main = (
        soup.select_one("main") or soup.select_one("article")
        or soup.select_one("#main-content") or soup.select_one(".main-content")
    )
    target = main if main else soup
    for tag in target(["script", "style", "nav", "footer", "header",
                        "aside", "noscript"]):
        tag.decompose()
    raw = target.get_text(separator="\n", strip=True)
    lines, seen = [], set()
    skip = {"skip to main content", "back to top", "donate", "subscribe"}
    for line in raw.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if not line or len(line) <= 2 or line.lower() in skip:
            continue
        if line in seen:
            continue
        seen.add(line)
        lines.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def is_insurance_relevant(text: str, min_matches: int = 3) -> bool:
    lower = text.lower()
    return sum(1 for kw in INSURANCE_KEYWORDS if kw in lower) >= min_matches


def load_visited(out_dir: Path) -> set[str]:
    visited = set()
    for p in out_dir.glob("*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if "url" in d:
                visited.add(d["url"])
        except Exception:
            pass
    return visited


def save_page(out_dir: Path, source: str, url: str, title: str, text: str):
    slug = hashlib.md5(url.encode()).hexdigest()[:12]
    record = {"source": source, "url": url, "title": title, "text": text}
    (out_dir / f"{slug}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def crawl_source(name: str, config: dict) -> int:
    out_dir = RAW_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)
    session = make_session()
    visited = load_visited(out_dir)
    queue = [s for s in config["seeds"] if s not in visited]
    saved = 0

    print(f"\n[{name}] {len(visited)} already saved, resuming...")

    while queue and saved < config["max_pages"]:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)

        resp = fetch(url, session)
        if not resp:
            continue

        text = extract_text(resp.text)
        if len(text) < 250:
            continue

        if not is_insurance_relevant(text):
            print(f"  [not relevant] {url}")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        title = soup.title.get_text(strip=True) if soup.title else ""
        save_page(out_dir, name, url, title, text)
        saved += 1
        print(f"  [{name}][{saved}] {url}")

        for a in soup.find_all("a", href=True):
            link = urljoin(url, a["href"])
            clean = urlparse(link)._replace(fragment="", query="").geturl()
            if any(clean.startswith(ex) for ex in config.get("exclude_prefixes", [])):
                continue
            if any(clean.startswith(p) for p in config["allowed_prefixes"]) and clean not in visited:
                queue.append(clean)

        time.sleep(DELAY + random.uniform(0, 0.5))

    print(f"  -> [{name}] {saved} pages saved\n")
    return saved


# ── Source definitions ────────────────────────────────────────────────────────

SOURCES = {
    "naic": {
        "seeds": [
            "https://content.naic.org/consumer",
            "https://content.naic.org/consumer/health-insurance.htm",
            "https://content.naic.org/consumer/shopping-health-plan.htm",
            "https://content.naic.org/consumer/understanding-your-health-insurance.htm",
            "https://content.naic.org/consumer/appeals-health-insurance.htm",
        ],
        "allowed_prefixes": ["https://content.naic.org/consumer"],
        "exclude_prefixes": [
            "https://content.naic.org/consumer/find-insurance-department",
            "https://content.naic.org/consumer/file-complaint",
        ],
        "max_pages": 80,
    },
    "georgetown_health": {
        "seeds": [
            "https://www.healthinsurance.org/faqs/",
            "https://www.healthinsurance.org/obamacare/",
            "https://www.healthinsurance.org/medicaid/",
            "https://www.healthinsurance.org/medicare/",
            "https://www.healthinsurance.org/cobra/",
            "https://www.healthinsurance.org/short-term-health-insurance/",
        ],
        "allowed_prefixes": ["https://www.healthinsurance.org/"],
        "exclude_prefixes": [
            "https://www.healthinsurance.org/about/",
            "https://www.healthinsurance.org/contact/",
            "https://www.healthinsurance.org/authors/",
            "https://www.healthinsurance.org/wp-content/",
            "https://www.healthinsurance.org/privacy-policy/",
            "https://www.healthinsurance.org/terms-of-use/",
        ],
        "max_pages": 120,
    },
    "families_usa": {
        "seeds": [
            "https://familiesusa.org/issues/health-coverage/",
            "https://familiesusa.org/issues/medicaid/",
            "https://familiesusa.org/issues/aca/",
            "https://familiesusa.org/resources/",
        ],
        "allowed_prefixes": [
            "https://familiesusa.org/issues/",
            "https://familiesusa.org/resources/",
        ],
        "exclude_prefixes": [
            "https://familiesusa.org/about/",
            "https://familiesusa.org/news/",
            "https://familiesusa.org/events/",
            "https://familiesusa.org/team/",
            "https://familiesusa.org/donate/",
        ],
        "max_pages": 80,
    },
    "medicare_rights": {
        "seeds": [
            "https://www.medicarerights.org/medicare-watch/",
            "https://www.medicarerights.org/medicare-interactive/",
            "https://www.medicarerights.org/get-answers/",
            "https://www.medicarerights.org/get-help/",
        ],
        "allowed_prefixes": [
            "https://www.medicarerights.org/medicare-watch/",
            "https://www.medicarerights.org/medicare-interactive/",
            "https://www.medicarerights.org/get-answers/",
        ],
        "exclude_prefixes": [
            "https://www.medicarerights.org/about/",
            "https://www.medicarerights.org/donate/",
            "https://www.medicarerights.org/newsroom/",
            "https://www.medicarerights.org/our-work/",
        ],
        "max_pages": 100,
    },
    "cbpp_health": {
        "seeds": [
            "https://www.cbpp.org/health/medicaid",
            "https://www.cbpp.org/health/affordable-care-act",
            "https://www.cbpp.org/health/premium-tax-credits",
            "https://www.cbpp.org/health/marketplace",
        ],
        "allowed_prefixes": ["https://www.cbpp.org/health/"],
        "exclude_prefixes": [
            "https://www.cbpp.org/about/",
            "https://www.cbpp.org/careers/",
            "https://www.cbpp.org/events/",
        ],
        "max_pages": 80,
    },
    "mental_health_america": {
        "seeds": [
            "https://mhanational.org/get-involved/advocacy/insurance-parity",
            "https://mhanational.org/issues/insurance-parity",
            "https://mhanational.org/health-insurance",
            "https://mhanational.org/mental-health-parity",
        ],
        "allowed_prefixes": [
            "https://mhanational.org/get-involved/advocacy/",
            "https://mhanational.org/issues/",
            "https://mhanational.org/health-insurance",
            "https://mhanational.org/mental-health-parity",
        ],
        "exclude_prefixes": [
            "https://mhanational.org/about/",
            "https://mhanational.org/donate/",
            "https://mhanational.org/events/",
        ],
        "max_pages": 50,
    },
    "american_cancer_society": {
        "seeds": [
            "https://www.cancer.org/support-programs-and-services/patient-support/navigating-insurance.html",
            "https://www.cancer.org/support-programs-and-services/financial-and-insurance-matters.html",
            "https://www.cancer.org/cancer/managing-cancer/treatment-types/understanding-your-insurance.html",
        ],
        "allowed_prefixes": [
            "https://www.cancer.org/support-programs-and-services/",
            "https://www.cancer.org/cancer/managing-cancer/treatment-types/understanding-your-insurance",
        ],
        "exclude_prefixes": [
            "https://www.cancer.org/about-us/",
            "https://www.cancer.org/research/",
            "https://www.cancer.org/cancer/types/",
        ],
        "max_pages": 60,
    },
    "pan_foundation": {
        "seeds": [
            "https://www.panfoundation.org/resources/",
            "https://www.panfoundation.org/resources/understanding-health-insurance/",
            "https://www.panfoundation.org/resources/patient-assistance/",
            "https://www.panfoundation.org/resources/managing-out-of-pocket-costs/",
        ],
        "allowed_prefixes": ["https://www.panfoundation.org/resources/"],
        "exclude_prefixes": [
            "https://www.panfoundation.org/about/",
            "https://www.panfoundation.org/donate/",
            "https://www.panfoundation.org/disease-funds/",
        ],
        "max_pages": 60,
    },
}


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Scrape additional advocacy organizations")
    p.add_argument(
        "--sources",
        nargs="+",
        choices=list(SOURCES) + ["all"],
        default=["all"],
    )
    args = p.parse_args()

    targets = list(SOURCES) if "all" in args.sources else args.sources
    for name in targets:
        crawl_source(name, SOURCES[name])
