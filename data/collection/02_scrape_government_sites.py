"""
Day 3-4: Scrape government help centers — Healthcare.gov, Medicare.gov, Medicaid.gov, DOL.
All content is public domain. Saves raw HTML + extracted text per page.
"""

import json
import time
import hashlib
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

RAW_DIR = Path(__file__).parent.parent / "raw"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; HealthInsuranceResearchBot/1.0; "
        "+https://github.com/your-repo)"
    )
}
DELAY = 1.5  # seconds between requests — be polite


# ── Helpers ───────────────────────────────────────────────────────────────────

def fetch(url: str, session: requests.Session) -> requests.Response | None:
    try:
        resp = session.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        return resp
    except Exception as e:
        print(f"  WARN: {url} -> {e}")
        return None


def extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    # Prefer the main content region when the site provides one.
    main = (
        soup.select_one("main")
        or soup.select_one("article")
        or soup.select_one("#main-content")
        or soup.select_one(".main-content")
    )
    target = main if main else soup

    for tag in target(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()

    text = target.get_text(separator="\n", strip=True)
    lines = []
    seen = set()
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        if line in seen:
            continue
        if line in {
            "Skip to main content",
            "Official websites use .gov",
            "Secure .gov websites use HTTPS",
            "Back to glossary",
        }:
            continue
        seen.add(line)
        lines.append(line)
    return "\n".join(lines)


def save_page(out_dir: Path, url: str, title: str, text: str) -> None:
    slug = hashlib.md5(url.encode()).hexdigest()[:12]
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    page_type = path.strip("/").split("/")[0] if path.strip("/") else "root"
    record = {
        "url": url,
        "title": title,
        "path": path,
        "page_type": page_type,
        "text": text,
    }
    with open(out_dir / f"{slug}.json", "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)


def crawl_site(
    seed_urls: list[str],
    allowed_prefix: str,
    out_dir: Path,
    max_pages: int = 500,
) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    visited: set[str] = set()
    queue: list[str] = list(seed_urls)
    saved = 0

    while queue and saved < max_pages:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)

        resp = fetch(url, session)
        if not resp:
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        text = extract_text(resp.text)
        if len(text) > 200:
            title = soup.title.get_text(strip=True) if soup.title else ""
            save_page(out_dir, url, title, text)
            saved += 1
            print(f"  [{saved}] {url}")

        for a in soup.find_all("a", href=True):
            link = urljoin(url, a["href"])
            parsed = urlparse(link)
            clean = parsed._replace(fragment="", query="").geturl()
            if clean.startswith(allowed_prefix) and clean not in visited:
                queue.append(clean)

        time.sleep(DELAY)

    print(f"  -> Saved {saved} pages from {allowed_prefix}\n")
    return saved


# ── Site-specific scrapers ────────────────────────────────────────────────────

def scrape_healthcare_gov():
    return crawl_site(
        seed_urls=[
            "https://www.healthcare.gov/glossary/",
            "https://www.healthcare.gov/quick-guide/",
            "https://www.healthcare.gov/coverage/",
            "https://www.healthcare.gov/lower-costs/",
            "https://www.healthcare.gov/life-changes/",
            "https://www.healthcare.gov/preventive-care-adults/",
        ],
        allowed_prefix="https://www.healthcare.gov/",
        out_dir=RAW_DIR / "healthcare_gov",
        max_pages=400,
    )


def scrape_medicare_gov():
    return crawl_site(
        seed_urls=[
            "https://www.medicare.gov/what-medicare-covers",
            "https://www.medicare.gov/basics/",
            "https://www.medicare.gov/sign-up-change-plans/",
            "https://www.medicare.gov/claims-appeals/",
            "https://www.medicare.gov/supplements-other-insurance/",
            "https://www.medicare.gov/drug-coverage-part-d/",
        ],
        allowed_prefix="https://www.medicare.gov/",
        out_dir=RAW_DIR / "medicare_gov",
        max_pages=400,
    )


def scrape_medicaid_gov():
    return crawl_site(
        seed_urls=[
            "https://www.medicaid.gov/medicaid/index.html",
            "https://www.medicaid.gov/medicaid/eligibility/index.html",
            "https://www.medicaid.gov/medicaid/benefits/index.html",
            "https://www.medicaid.gov/chip/index.html",
        ],
        allowed_prefix="https://www.medicaid.gov/",
        out_dir=RAW_DIR / "medicaid_gov",
        max_pages=200,
    )


def scrape_dol_ebsa():
    return crawl_site(
        seed_urls=[
            "https://www.dol.gov/agencies/ebsa/about-ebsa/our-activities/resource-center",
            "https://www.dol.gov/general/topic/health-plans",
            "https://www.dol.gov/agencies/ebsa/workers-and-families/changing-jobs-and-job-loss",
        ],
        allowed_prefix="https://www.dol.gov/",
        out_dir=RAW_DIR / "dol_ebsa",
        max_pages=150,
    )


def scrape_irs_publications():
    """Fetch IRS Publication 969 (HSA / FSA rules) as plain text."""
    pub_urls = [
        "https://www.irs.gov/publications/p969",
        "https://www.irs.gov/taxtopics/tc502",
        "https://www.irs.gov/taxtopics/tc751",
    ]
    out_dir = RAW_DIR / "irs"
    out_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    for url in pub_urls:
        resp = fetch(url, session)
        if resp:
            text = extract_text(resp.text)
            save_page(out_dir, url, text)
            print(f"  Saved: {url}")
            time.sleep(DELAY)
    print(f"  -> Saved IRS publications to {out_dir}\n")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scrape government insurance websites")
    parser.add_argument("--healthcare", action="store_true")
    parser.add_argument("--medicare", action="store_true")
    parser.add_argument("--medicaid", action="store_true")
    parser.add_argument("--dol", action="store_true")
    parser.add_argument("--irs", action="store_true")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    if args.all or args.healthcare:
        scrape_healthcare_gov()
    if args.all or args.medicare:
        scrape_medicare_gov()
    if args.all or args.medicaid:
        scrape_medicaid_gov()
    if args.all or args.dol:
        scrape_dol_ebsa()
    if args.all or args.irs:
        scrape_irs_publications()
