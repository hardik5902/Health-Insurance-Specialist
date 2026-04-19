"""
Scrape state-based marketplace (SBM) sites not covered in 06_collect_state_resources.py.
These 7 states run their own marketplaces with unique enrollment rules.

States: Massachusetts, Colorado, Washington, Maryland, New Jersey, Minnesota, Virginia

Run:
    python 09_collect_new_state_marketplaces.py --all
    python 09_collect_new_state_marketplaces.py --states massachusetts colorado
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

RAW_DIR = Path(__file__).parent.parent / "raw" / "state_marketplaces"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; HealthInsuranceResearchBot/1.0; "
        "Academic/non-commercial research)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
DELAY = 1.5


def make_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3, backoff_factor=1.0,
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
    for line in raw.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if not line or len(line) <= 2:
            continue
        if line in seen:
            continue
        seen.add(line)
        lines.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


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


def save_page(out_dir: Path, state: str, url: str, title: str, text: str):
    slug = hashlib.md5(url.encode()).hexdigest()[:12]
    record = {"state": state, "url": url, "title": title, "text": text}
    (out_dir / f"{slug}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def crawl_state(state: str, config: dict) -> int:
    out_dir = RAW_DIR / state
    out_dir.mkdir(parents=True, exist_ok=True)
    session = make_session()
    visited = load_visited(out_dir)
    queue = [s for s in config["seeds"] if s not in visited]
    saved = 0

    print(f"\n[{state}] {len(visited)} already saved, resuming...")

    while queue and saved < config["max_pages"]:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)

        resp = fetch(url, session)
        if not resp:
            continue

        text = extract_text(resp.text)
        if len(text) < 200:
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        title = soup.title.get_text(strip=True) if soup.title else ""
        save_page(out_dir, state, url, title, text)
        saved += 1
        print(f"  [{state}][{saved}] {url}")

        for a in soup.find_all("a", href=True):
            link = urljoin(url, a["href"])
            clean = urlparse(link)._replace(fragment="", query="").geturl()
            if any(clean.startswith(ex) for ex in config.get("exclude_prefixes", [])):
                continue
            if any(clean.startswith(p) for p in config["allowed_prefixes"]) and clean not in visited:
                queue.append(clean)

        time.sleep(DELAY + random.uniform(0, 0.5))

    print(f"  -> [{state}] {saved} pages saved\n")
    return saved


# ── State marketplace definitions ─────────────────────────────────────────────

STATE_SOURCES = {
    "massachusetts": {
        "seeds": [
            "https://www.mahealthconnector.org/help-center/",
            "https://www.mahealthconnector.org/help-center/learn-about-health-insurance/",
            "https://www.mahealthconnector.org/help-center/learn-about-dental-insurance/",
            "https://www.mahealthconnector.org/health-plans/",
            "https://www.mahealthconnector.org/shop-and-compare/",
        ],
        "allowed_prefixes": [
            "https://www.mahealthconnector.org/help-center/",
            "https://www.mahealthconnector.org/health-plans/",
        ],
        "exclude_prefixes": [
            "https://www.mahealthconnector.org/about/",
            "https://www.mahealthconnector.org/news/",
            "https://www.mahealthconnector.org/for-employers/",
        ],
        "max_pages": 80,
    },
    "colorado": {
        "seeds": [
            "https://connectforhealthco.com/get-started/learn/",
            "https://connectforhealthco.com/get-started/why-health-insurance/",
            "https://connectforhealthco.com/get-started/whats-covered/",
            "https://connectforhealthco.com/get-started/how-insurance-works/",
            "https://connectforhealthco.com/find-assistance/",
        ],
        "allowed_prefixes": [
            "https://connectforhealthco.com/get-started/",
            "https://connectforhealthco.com/find-assistance/",
        ],
        "exclude_prefixes": [
            "https://connectforhealthco.com/about/",
            "https://connectforhealthco.com/news/",
            "https://connectforhealthco.com/for-employers/",
        ],
        "max_pages": 70,
    },
    "washington": {
        "seeds": [
            "https://www.wahealthplanfinder.org/HBEWeb/Anka/healthInsuranceBasics.html",
            "https://www.wahealthplanfinder.org/HBEWeb/Anka/helpAndFAQs.html",
            "https://www.wahealthplanfinder.org/HBEWeb/Anka/learnAboutHealthInsurance.html",
        ],
        "allowed_prefixes": [
            "https://www.wahealthplanfinder.org/",
        ],
        "exclude_prefixes": [
            "https://www.wahealthplanfinder.org/HBEWeb/Anka/login",
            "https://www.wahealthplanfinder.org/HBEWeb/Anka/createAccount",
        ],
        "max_pages": 60,
    },
    "maryland": {
        "seeds": [
            "https://www.marylandhealthconnection.gov/health-coverage/",
            "https://www.marylandhealthconnection.gov/health-coverage/individuals-and-families/",
            "https://www.marylandhealthconnection.gov/learn/",
            "https://www.marylandhealthconnection.gov/learn/understanding-health-coverage/",
            "https://www.marylandhealthconnection.gov/faq/",
        ],
        "allowed_prefixes": [
            "https://www.marylandhealthconnection.gov/health-coverage/",
            "https://www.marylandhealthconnection.gov/learn/",
            "https://www.marylandhealthconnection.gov/faq/",
        ],
        "exclude_prefixes": [
            "https://www.marylandhealthconnection.gov/about/",
            "https://www.marylandhealthconnection.gov/news/",
            "https://www.marylandhealthconnection.gov/for-employers/",
        ],
        "max_pages": 70,
    },
    "new_jersey": {
        "seeds": [
            "https://www.getcoverednj.gov/learn/",
            "https://www.getcoverednj.gov/learn/how-does-health-insurance-work/",
            "https://www.getcoverednj.gov/learn/types-of-health-plans/",
            "https://www.getcoverednj.gov/learn/financial-help/",
            "https://www.getcoverednj.gov/faq/",
        ],
        "allowed_prefixes": [
            "https://www.getcoverednj.gov/learn/",
            "https://www.getcoverednj.gov/faq/",
        ],
        "exclude_prefixes": [
            "https://www.getcoverednj.gov/about/",
            "https://www.getcoverednj.gov/news/",
            "https://www.getcoverednj.gov/for-employers/",
        ],
        "max_pages": 70,
    },
    "minnesota": {
        "seeds": [
            "https://www.mnsure.org/help/",
            "https://www.mnsure.org/help/faq/",
            "https://www.mnsure.org/help/learn-about-coverage/",
            "https://www.mnsure.org/help/learn-about-coverage/types-of-coverage.jsp",
            "https://www.mnsure.org/help/learn-about-coverage/how-coverage-works.jsp",
        ],
        "allowed_prefixes": [
            "https://www.mnsure.org/help/",
        ],
        "exclude_prefixes": [
            "https://www.mnsure.org/about/",
            "https://www.mnsure.org/news/",
            "https://www.mnsure.org/help/assisters/",
        ],
        "max_pages": 70,
    },
    "virginia": {
        "seeds": [
            "https://www.marketplace.virginia.gov/learn/",
            "https://www.marketplace.virginia.gov/learn/how-health-insurance-works/",
            "https://www.marketplace.virginia.gov/learn/financial-help/",
            "https://www.marketplace.virginia.gov/faq/",
        ],
        "allowed_prefixes": [
            "https://www.marketplace.virginia.gov/learn/",
            "https://www.marketplace.virginia.gov/faq/",
        ],
        "exclude_prefixes": [
            "https://www.marketplace.virginia.gov/about/",
            "https://www.marketplace.virginia.gov/news/",
        ],
        "max_pages": 60,
    },
}


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Collect state-based marketplace content")
    p.add_argument(
        "--states",
        nargs="+",
        choices=list(STATE_SOURCES) + ["all"],
        default=["all"],
    )
    args = p.parse_args()

    targets = list(STATE_SOURCES) if "all" in args.states else args.states
    for state in targets:
        crawl_state(state, STATE_SOURCES[state])
