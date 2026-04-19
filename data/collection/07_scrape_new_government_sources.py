"""
Scrape additional government sources not covered in 02_scrape_government_sites.py.
Sources: CMS CCIIO, HHS.gov, SAMHSA, Benefits.gov, No Surprises Act (cms.gov/nosurprises)
All content is public domain (.gov).

Run:
    python 07_scrape_new_government_sources.py --all
    python 07_scrape_new_government_sources.py --cciio --nosurprises
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

RAW_DIR = Path(__file__).parent.parent / "raw" / "government_additional"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/135.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
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
    skip = {
        "skip to main content", "official websites use .gov",
        "secure .gov websites use https", "back to top",
    }
    for line in raw.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if not line or line.lower() in skip or len(line) <= 2:
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


def save_page(out_dir: Path, source: str, url: str, title: str, text: str):
    slug = hashlib.md5(url.encode()).hexdigest()[:12]
    record = {"source": source, "url": url, "title": title, "text": text}
    (out_dir / f"{slug}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def crawl(
    name: str,
    seeds: list[str],
    allowed_prefixes: list[str],
    exclude_prefixes: list[str],
    out_dir: Path,
    max_pages: int = 200,
) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    session = make_session()
    visited = load_visited(out_dir)
    queue = [s for s in seeds if s not in visited]
    saved = 0

    print(f"\n[{name}] {len(visited)} already saved, resuming...")

    while queue and saved < max_pages:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)

        resp = fetch(url, session)
        if not resp:
            continue

        content_type = resp.headers.get("Content-Type", "")
        if "text/html" not in content_type:
            continue

        text = extract_text(resp.text)
        if len(text) < 200:
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        title = soup.title.get_text(strip=True) if soup.title else ""
        save_page(out_dir, name, url, title, text)
        saved += 1
        print(f"  [{name}][{saved}] {url}")

        for a in soup.find_all("a", href=True):
            link = urljoin(url, a["href"])
            clean = urlparse(link)._replace(fragment="", query="").geturl()
            if any(clean.startswith(ex) for ex in exclude_prefixes):
                continue
            if any(clean.startswith(p) for p in allowed_prefixes) and clean not in visited:
                queue.append(clean)

        time.sleep(DELAY + random.uniform(0, 0.5))

    print(f"  -> [{name}] {saved} pages saved\n")
    return saved


# ── Source-specific scrapers ──────────────────────────────────────────────────

def scrape_cms_cciio():
    """ACA consumer protections, plan rules, essential health benefits."""
    return crawl(
        name="cms_cciio",
        seeds=[
            "https://www.cms.gov/cciio/programs-and-initiatives/health-insurance-market-reforms",
            "https://www.cms.gov/cciio/programs-and-initiatives/other-insurance-protections",
            "https://www.cms.gov/cciio/programs-and-initiatives/health-insurance-marketplaces",
            "https://www.cms.gov/cciio/programs-and-initiatives/premium-stabilization-programs",
            "https://www.cms.gov/CCIIO/Resources/Consumer-Assistance-Grants",
        ],
        allowed_prefixes=["https://www.cms.gov/cciio/"],
        exclude_prefixes=[
            "https://www.cms.gov/cciio/news-events/",
            "https://www.cms.gov/cciio/about/",
            "https://www.cms.gov/cciio/regulations-and-guidance/downloads/",
            "https://www.cms.gov/cciio/programs-and-initiatives/premium-stabilization-programs/downloads/",
            "https://www.cms.gov/cciio/programs-and-initiatives/premium-stabilization-programs/the-transitional-reinsurance-program/downloads/",
        ],
        out_dir=RAW_DIR / "cms_cciio",
        max_pages=150,
    )


def scrape_hhs_healthcare():
    """Federal consumer health guides from HHS."""
    return crawl(
        name="hhs_healthcare",
        seeds=[
            "https://www.hhs.gov/healthcare/index.html",
            "https://www.hhs.gov/healthcare/about-the-aca/index.html",
            "https://www.hhs.gov/healthcare/rights/index.html",
            "https://www.hhs.gov/healthcare/preventive-care/index.html",
        ],
        allowed_prefixes=["https://www.hhs.gov/healthcare/"],
        exclude_prefixes=[
            "https://www.hhs.gov/healthcare/news/",
            "https://www.hhs.gov/healthcare/leadership/",
        ],
        out_dir=RAW_DIR / "hhs_healthcare",
        max_pages=100,
    )


def scrape_samhsa():
    """Mental health and substance abuse coverage, parity law guides."""
    return crawl(
        name="samhsa",
        seeds=[
            "https://www.samhsa.gov/find-help/health-coverage-benefits",
            "https://www.samhsa.gov/mental-health/mental-health-coverage",
            "https://www.samhsa.gov/health-financing",
            "https://www.samhsa.gov/mental-health-substance-use-co-occurring-disorders",
        ],
        allowed_prefixes=[
            "https://www.samhsa.gov/find-help/health-coverage-benefits",
            "https://www.samhsa.gov/mental-health/mental-health-coverage",
            "https://www.samhsa.gov/health-financing",
        ],
        exclude_prefixes=[
            "https://www.samhsa.gov/newsroom/",
            "https://www.samhsa.gov/grants/",
            "https://www.samhsa.gov/data/",
        ],
        out_dir=RAW_DIR / "samhsa",
        max_pages=80,
    )


def scrape_benefits_gov():
    """Cross-program benefit eligibility — Medicaid, Medicare, ACA together."""
    return crawl(
        name="benefits_gov",
        seeds=[
            "https://www.benefits.gov/benefit/1551",   # Medicaid
            "https://www.benefits.gov/benefit/4412",   # CHIP
            "https://www.benefits.gov/benefit/615",    # Medicare Part A
            "https://www.benefits.gov/benefit/617",    # Medicare Part B
            "https://www.benefits.gov/benefit/1019",   # Medicare Part D
            "https://www.benefits.gov/benefit/752",    # ACA Marketplace
        ],
        allowed_prefixes=["https://www.benefits.gov/benefit/"],
        exclude_prefixes=[],
        out_dir=RAW_DIR / "benefits_gov",
        max_pages=60,
    )


def scrape_no_surprises_act():
    """No Surprises Act — surprise billing protections (major 2022 law)."""
    return crawl(
        name="no_surprises_act",
        seeds=[
            "https://www.cms.gov/nosurprises",
            "https://www.cms.gov/nosurprises/consumers",
            "https://www.cms.gov/nosurprises/providers-and-facilities",
            "https://www.cms.gov/nosurprises/Additional-Resources",
        ],
        allowed_prefixes=["https://www.cms.gov/nosurprises"],
        exclude_prefixes=[
            "https://www.cms.gov/nosurprises/federal-idrs",
        ],
        out_dir=RAW_DIR / "no_surprises_act",
        max_pages=60,
    )


# ── Entry point ───────────────────────────────────────────────────────────────

SOURCES = {
    "cciio": scrape_cms_cciio,
    "hhs": scrape_hhs_healthcare,
    "samhsa": scrape_samhsa,
    "benefits": scrape_benefits_gov,
    "nosurprises": scrape_no_surprises_act,
}

if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Scrape additional government insurance sources")
    for key in SOURCES:
        p.add_argument(f"--{key}", action="store_true")
    p.add_argument("--all", action="store_true")
    args = p.parse_args()

    for key, fn in SOURCES.items():
        if args.all or getattr(args, key):
            fn()
