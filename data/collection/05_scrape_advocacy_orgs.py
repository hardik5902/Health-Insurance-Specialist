"""
Scrape nonprofit and advocacy organization insurance guides.
Sources: KFF, Patient Advocate Foundation, HealthInsurance.org, NeedyMeds.
"""

import json
import time
import hashlib
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

RAW_DIR = Path(__file__).parent.parent / "raw" / "advocacy"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/135.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}
DELAY = 2.0

SOURCES = {
    "kff": {
        "seeds": [
            "https://kff.org/health-policy-101/",
            "https://kff.org/patient-consumer-protections/health-policy-101-the-regulation-of-private-health-insurance/",
            "https://kff.org/health-costs/health-policy-101-employer-sponsored-health-insurance/",
            "https://kff.org/affordable-care-act/health-policy-101-the-affordable-care-act/",
            "https://kff.org/faqs/faqs-health-insurance-marketplace-and-the-aca/",
        ],
        "allowed_prefixes": [
            "https://kff.org/health-policy-101/",
            "https://kff.org/patient-consumer-protections/",
            "https://kff.org/health-costs/",
            "https://kff.org/affordable-care-act/",
            "https://kff.org/medicare/",
            "https://kff.org/medicaid/",
            "https://kff.org/faqs/",
        ],
        "exclude_prefixes": [
            "https://kff.org/person/",
            "https://kff.org/people",
            "https://kff.org/about-us/",
            "https://kff.org/events/",
            "https://kff.org/content-type/",
            "https://kff.org/topic/",
            "https://kff.org/topics/",
            "https://kff.org/interactive/",
            "https://kff.org/media-resources/",
            "https://kff.org/series/",
        ],
        "max_pages": 120,
    },
    "healthinsurance_org": {
        "seeds": [
            "https://www.healthinsurance.org/learn/",
            "https://www.healthinsurance.org/obamacare/",
            "https://www.healthinsurance.org/glossary/",
        ],
        "allowed_prefixes": ["https://www.healthinsurance.org/"],
        "exclude_prefixes": [
            "https://www.healthinsurance.org/privacy-policy/",
            "https://www.healthinsurance.org/terms-of-use/",
            "https://www.healthinsurance.org/contact/",
            "https://www.healthinsurance.org/about/",
            "https://www.healthinsurance.org/authors/",
            "https://www.healthinsurance.org/newsroom/",
            "https://www.healthinsurance.org/wp-content/",
        ],
        "max_pages": 200,
    },
    "patient_advocate": {
        "seeds": [
            "https://www.patientadvocate.org/explore-our-resources/",
            "https://www.patientadvocate.org/explore-our-resources/the-language-of-insurance/",
            "https://www.patientadvocate.org/explore-our-resources/insurance-denials-appeals/where-to-start-if-insurance-has-denied-your-service-and-will-not-pay/",
            "https://www.patientadvocate.org/explore-our-resources/insurance-denials-appeals/things-to-include-in-your-appeal-letter/",
            "https://www.patientadvocate.org/learn-about-medicare/",
        ],
        "allowed_prefixes": [
            "https://www.patientadvocate.org/explore-our-resources/",
            "https://www.patientadvocate.org/learn-about-medicare/",
            "https://www.patientadvocate.org/download-view/",
            "https://www.patientadvocate.org/appeals-denials-wizard/",
        ],
        "exclude_prefixes": [
            "https://www.patientadvocate.org/get-involved/",
            "https://www.patientadvocate.org/learn-about-us/",
            "https://www.patientadvocate.org/contact/",
            "https://www.patientadvocate.org/request-paf-assistance/",
            "https://www.patientadvocate.org/lbmn_archive/",
            "https://www.patientadvocate.org/patient-privacy",
            "https://www.patientadvocate.org/privacy-policy",
            "https://www.patientadvocate.org/terms-of-use",
            "https://www.patientadvocate.org/explore-our-resources/order-print-copies-of-paf-publications/",
            "https://www.patientadvocate.org/explore-our-resources/order-brochures-about-pafs-services/",
            "https://www.patientadvocate.org/explore-our-resources/order-print-copies-of-pafs-spanish-publications/",
        ],
        "max_pages": 100,
    },
    "needymeds": {
        "seeds": [
            "https://blog.needymeds.org/category/insurance/",
            "https://blog.needymeds.org/2013/11/06/all-about-the-childrens-health-insurance-program-chip/",
            "https://blog.needymeds.org/2020/03/04/all-about-the-needymeds-drug-discount-card/",
            "https://blog.needymeds.org/2025/04/09/medicare-2026-what-you-need-to-know-about-plan-changes-next-year/",
            "https://blog.needymeds.org/2025/03/24/understanding-the-medicare-part-d-donut-hole-in-2025/",
        ],
        "allowed_prefixes": [
            "https://blog.needymeds.org/category/insurance/",
            "https://blog.needymeds.org/",
        ],
        "exclude_prefixes": [
            "https://blog.needymeds.org/about/",
            "https://blog.needymeds.org/how-you-can-help/",
            "https://blog.needymeds.org/subscribe-2/",
            "https://blog.needymeds.org/page/",
            "https://blog.needymeds.org/category/",
            "https://blog.needymeds.org/tag/",
            "https://blog.needymeds.org/author/",
            "https://blog.needymeds.org/wp-content/",
        ],
        "url_keywords": [
            "insurance",
            "medicare",
            "medicaid",
            "chip",
            "aca",
            "healthcare",
            "health-care",
            "health-insurance",
            "drug-discount-card",
            "patient-assistance",
            "donut-hole",
            "open-enrollment",
        ],
        "max_pages": 40,
    },
}


def make_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def fetch(url: str, session: requests.Session):
    try:
        r = session.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"  WARN: {url} -> {e}")
        return None


def should_enqueue(url: str, config: dict) -> bool:
    if not any(url.startswith(prefix) for prefix in config["allowed_prefixes"]):
        return False
    if any(url.startswith(prefix) for prefix in config["exclude_prefixes"]):
        return False

    lower_url = url.lower()
    if "untitled_" in lower_url:
        return False
    if '"' in url:
        return False
    if lower_url.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg")):
        return False
    if lower_url.rstrip("/") == "https://blog.needymeds.org":
        return False

    keywords = config.get("url_keywords")
    if keywords and not any(keyword in lower_url for keyword in keywords):
        return False

    return True


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
    session = make_session()
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
            if should_enqueue(clean, config) and clean not in visited:
                queue.append(clean)

        time.sleep(DELAY)

    print(f"  -> {name}: {saved} pages saved\n")
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
