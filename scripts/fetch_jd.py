#!/usr/bin/env python3
"""
JD Fetcher — fetch a job posting URL and save the cleaned text to archive/.

Replaces the manual copy-paste step. Supports LinkedIn, Lever, Greenhouse,
Ashby, and most company career pages. Falls back gracefully when JavaScript
rendering is required.

Usage:
    python scripts/fetch_jd.py --url "https://jobs.lever.co/company/abc123"
    python scripts/fetch_jd.py --url "https://..." --company "Merge" --role "Solutions Engineer"
    python scripts/fetch_jd.py --url "https://..." --output archive/job-desc-merge-se.txt

Requirements:
    pip install requests beautifulsoup4
    (bs4 is optional but strongly recommended for cleaner text extraction)
"""

import argparse
import re
import sys
import urllib.request
import urllib.error
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_DIR = ROOT / "archive"

# ---- Optional imports -------------------------------------------------------
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False


# ---- URL patterns for known ATS platforms -----------------------------------
ATS_PATTERNS = {
    "lever":      r"jobs\.lever\.co",
    "greenhouse": r"boards\.greenhouse\.io|grnh\.se",
    "ashby":      r"jobs\.ashbyhq\.com",
    "linkedin":   r"linkedin\.com/jobs",
    "workday":    r"myworkdayjobs\.com",
    "icims":      r"icims\.com",
    "hibob":      r"careers\.hibob\.com",
}

# Common boilerplate to strip from fetched text
BOILERPLATE_PATTERNS = [
    r"Apply for this job.*",
    r"Share this job.*",
    r"Save job.*",
    r"Easy apply.*",
    r"Cookie.*policy.*",
    r"Privacy policy.*",
    r"\d+ applicants.*",
    r"Sign in to.*",
    r"Join.*to apply.*",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def detect_ats(url: str) -> str:
    """Return the detected ATS platform or 'unknown'."""
    for platform, pattern in ATS_PATTERNS.items():
        if re.search(pattern, url, re.IGNORECASE):
            return platform
    return "unknown"


def fetch_html(url: str, timeout: int = 15) -> str:
    """Fetch raw HTML from a URL."""
    if REQUESTS_AVAILABLE:
        try:
            response = requests.get(url, headers=HEADERS, timeout=timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            raise RuntimeError(f"requests fetch failed: {e}")
    else:
        # Fallback to stdlib urllib
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.URLError as e:
            raise RuntimeError(f"urllib fetch failed: {e}")


def html_to_text(html: str) -> str:
    """Convert HTML to clean plain text."""
    if BS4_AVAILABLE:
        soup = BeautifulSoup(html, "html.parser")
        # Remove script and style tags
        for tag in soup(["script", "style", "nav", "header", "footer", "meta", "noscript"]):
            tag.decompose()

        # Find main content container (best-effort heuristics)
        main = (
            soup.find("main") or
            soup.find(id=re.compile(r"job|content|description|posting", re.I)) or
            soup.find(class_=re.compile(r"job|content|description|posting", re.I)) or
            soup.body or
            soup
        )

        text = main.get_text(separator="\n")
    else:
        # Naive HTML strip with regex
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"&lt;", "<", text)
        text = re.sub(r"&gt;", ">", text)
        text = re.sub(r"&#\d+;", "", text)

    # Normalize whitespace
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            lines.append(line)

    text = "\n".join(lines)

    # Remove common boilerplate
    for pattern in BOILERPLATE_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.MULTILINE)

    # Collapse 3+ blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def infer_company_role_from_url(url: str) -> tuple[str, str]:
    """Heuristically extract company and role from URL path."""
    path = url.rstrip("/").split("?")[0].split("/")
    # Lever: jobs.lever.co/{company}/...
    # Greenhouse: boards.greenhouse.io/{company}/jobs/{id}
    # Ashby: jobs.ashbyhq.com/{company}/...
    company = "unknown"
    role = "unknown"

    lever_m = re.search(r"jobs\.lever\.co/([^/]+)", url)
    gh_m = re.search(r"greenhouse\.io/([^/]+)", url)
    ashby_m = re.search(r"ashbyhq\.com/([^/]+)", url)
    hibob_m = re.search(r"([\w-]+)\.careers\.hibob\.com", url)

    if lever_m:
        company = lever_m.group(1).replace("-", " ").title()
    elif gh_m:
        company = gh_m.group(1).replace("-", " ").title()
    elif ashby_m:
        company = ashby_m.group(1).replace("-", " ").title()
    elif hibob_m:
        company = hibob_m.group(1).replace("-", " ").title()

    return company, role


def build_output_path(company: str, role: str) -> Path:
    """Build the archive/ output path from company and role."""
    def slugify(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")

    company_slug = slugify(company) if company != "unknown" else "company"
    role_slug = slugify(role) if role != "unknown" else "role"
    filename = f"job-desc-{company_slug}-{role_slug}.txt"
    return ARCHIVE_DIR / filename


def fetch_jd(
    url: str,
    company: str | None = None,
    role: str | None = None,
    output_path: Path | None = None,
    timeout: int = 15,
) -> Path:
    """Fetch a job posting URL and save clean text to archive/."""
    platform = detect_ats(url)
    print(f"  Platform detected: {platform}")

    # LinkedIn requires JS rendering — warn and suggest manual copy
    if platform == "linkedin":
        print(
            "\n  [!] LinkedIn job pages require JavaScript rendering.\n"
            "  The fetched content may be incomplete or empty.\n"
            "  Recommended: open the LinkedIn posting, click 'See more' under the job\n"
            "  description, select all text, and paste into a .txt file in archive/.\n"
            "  Then run: python scripts/jd_parser.py --job archive/job-desc-{company}-{role}.txt\n"
        )

    print(f"  Fetching: {url}")
    try:
        html = fetch_html(url, timeout)
    except RuntimeError as e:
        # Try install hint
        if "requests" in str(e) and not REQUESTS_AVAILABLE:
            print(f"  [!] Install requests for better fetching: pip install requests beautifulsoup4")
        raise

    text = html_to_text(html)

    if len(text) < 200:
        print(
            f"\n  [!] Fetched content is very short ({len(text)} chars). "
            "The page may require JavaScript rendering.\n"
            "  Consider manually saving the job description to archive/."
        )

    # Determine company and role
    if not company or not role:
        inferred_company, inferred_role = infer_company_role_from_url(url)
        company = company or inferred_company
        role = role or inferred_role

    if not output_path:
        output_path = build_output_path(company, role)

    # Check if file already exists
    if output_path.exists():
        print(f"  [!] File already exists: {output_path}")
        overwrite = input("  Overwrite? [y/N]: ").strip().lower()
        if overwrite not in ("y", "yes"):
            print("  Skipped. Using existing file.")
            return output_path

    ARCHIVE_DIR.mkdir(exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    print(f"  Saved to: {output_path}  ({len(text):,} chars)")
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Fetch a job posting URL and save to archive/"
    )
    parser.add_argument("--url", required=True, help="Job posting URL")
    parser.add_argument("--company", help="Company name (overrides URL inference)")
    parser.add_argument("--role", help="Role name (overrides URL inference)")
    parser.add_argument("--output", help="Output file path (default: archive/job-desc-{company}-{role}.txt)")
    parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout in seconds (default: 15)")
    args = parser.parse_args()

    if not REQUESTS_AVAILABLE:
        print("  [!] 'requests' not installed. Falling back to stdlib urllib (less reliable).")
        print("  Install for better results: pip install requests beautifulsoup4\n")

    output_path = Path(args.output) if args.output else None

    try:
        saved_path = fetch_jd(
            url=args.url,
            company=args.company,
            role=args.role,
            output_path=output_path,
            timeout=args.timeout,
        )
    except RuntimeError as e:
        print(f"\n  [!] Fetch failed: {e}")
        print("  Consider manually saving the job description to archive/.")
        sys.exit(1)

    print(f"\nNext step: python scripts/evaluate.py --job {saved_path}")


if __name__ == "__main__":
    main()
