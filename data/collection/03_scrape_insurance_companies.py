"""
Weekend (Week 1): Scrape public member education content from major insurance companies.
Targets: UnitedHealthcare, Cigna, Kaiser Permanente, Aetna, Humana, Oscar Health.
"""

import json
import time
import hashlib
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

RAW_DIR = Path(__file__).parent.parent / "raw" / "insurance_companies"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; HealthInsuranceResearchBot/1.0; "
        "+https://github.com/your-repo)"
    )
}
DELAY = 2.0


# ── Crawler ───────────────────────────────────────────────────────────────────

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
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def save_page(out_dir: Path, url: str, text: str, company: str) -> None:
    slug = hashlib.md5(url.encode()).hexdigest()[:12]
    record = {"company": company, "url": url, "text": text}
    with open(out_dir / f"{slug}.json", "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)


def crawl(
    company: str,
    seed_urls: list[str],
    allowed_prefixes: list[str],
    max_pages: int = 200,
) -> int:
    out_dir = RAW_DIR / company.lower().replace(" ", "_")
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

        text = extract_text(resp.text)
        if len(text) > 300:
            save_page(out_dir, url, text, company)
            saved += 1
            print(f"  [{company}][{saved}] {url}")

        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            link = urljoin(url, a["href"])
            parsed = urlparse(link)
            clean = parsed._replace(fragment="", query="").geturl()
            if any(clean.startswith(p) for p in allowed_prefixes) and clean not in visited:
                queue.append(clean)

        time.sleep(DELAY)

    print(f"  -> {company}: {saved} pages saved\n")
    return saved


# ── Per-company scrapers ──────────────────────────────────────────────────────

def scrape_unitedhealthcare():
    crawl(
        company="UnitedHealthcare",
        seed_urls=[
            "https://www.uhc.com/health-and-wellness/health-topics/understanding-health-insurance",
            "https://www.uhc.com/understanding-your-insurance",
        ],
        allowed_prefixes=[
            "https://www.uhc.com/understanding-your-insurance",
            "https://www.uhc.com/health-and-wellness",
        ],
        max_pages=150,
    )


def scrape_cigna():
    crawl(
        company="Cigna",
        seed_urls=[
            "https://www.cigna.com/knowledge-center/",
            "https://www.cigna.com/knowledge-center/insurance-basics",
            "https://www.cigna.com/knowledge-center/hw/",
        ],
        allowed_prefixes=["https://www.cigna.com/knowledge-center/"],
        max_pages=200,
    )


def scrape_kaiser():
    crawl(
        company="Kaiser Permanente",
        seed_urls=[
            "https://healthy.kaiserpermanente.org/health-wellness/health-encyclopedia",
            "https://healthy.kaiserpermanente.org/health-wellness",
        ],
        allowed_prefixes=[
            "https://healthy.kaiserpermanente.org/health-wellness",
        ],
        max_pages=200,
    )


def scrape_aetna():
    crawl(
        company="Aetna",
        seed_urls=[
            "https://www.aetna.com/individuals-families/using-your-aetna-benefits.html",
            "https://www.aetna.com/individuals-families/understanding-health-insurance.html",
        ],
        allowed_prefixes=[
            "https://www.aetna.com/individuals-families/",
        ],
        max_pages=150,
    )


def scrape_humana():
    crawl(
        company="Humana",
        seed_urls=[
            "https://www.humana.com/learning-center",
            "https://www.humana.com/medicare/resources",
        ],
        allowed_prefixes=[
            "https://www.humana.com/learning-center",
            "https://www.humana.com/medicare/resources",
        ],
        max_pages=150,
    )


def scrape_oscar():
    crawl(
        company="Oscar Health",
        seed_urls=[
            "https://www.hioscar.com/blog",
            "https://www.hioscar.com/learn",
        ],
        allowed_prefixes=[
            "https://www.hioscar.com/blog",
            "https://www.hioscar.com/learn",
        ],
        max_pages=100,
    )


# ── Entry point ───────────────────────────────────────────────────────────────

COMPANIES = {
    "unitedhealthcare": scrape_unitedhealthcare,
    "cigna": scrape_cigna,
    "kaiser": scrape_kaiser,
    "aetna": scrape_aetna,
    "humana": scrape_humana,
    "oscar": scrape_oscar,
}

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scrape insurance company education content")
    parser.add_argument(
        "--companies",
        nargs="+",
        choices=list(COMPANIES) + ["all"],
        default=["all"],
        help="Which companies to scrape",
    )
    args = parser.parse_args()

    targets = list(COMPANIES.keys()) if "all" in args.companies else args.companies
    for name in targets:
        COMPANIES[name]()
