#!/usr/bin/env python3
"""
JD Parser — extracts structured information from raw job description text.

Reads a job description text file and outputs a structured YAML file
containing: company, role, seniority, required skills, preferred skills,
responsibilities, and raw keywords. This pre-parsed output feeds into
scorer.py and generate_resume.py to reduce LLM reasoning load.

Usage:
    python scripts/jd_parser.py --job archive/job-desc-hibob-implementation-manager.txt
    python scripts/jd_parser.py --job archive/job-desc-hibob.txt --company HiBob --role "Implementation Manager"
    python scripts/jd_parser.py --job archive/job-desc-hibob.txt --output archive/jd-parsed-hibob.yaml
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_DIR = ROOT / "archive"

# ---- Section header patterns ------------------------------------------------
# Order matters: more specific patterns first.
SECTION_PATTERNS = [
    (r"(?i)^(requirements?|qualifications?|required skills?|required experience"
     r"|required competenc|specialized knowledge|skills? (and|&) requirements?"
     r"|what you.ll bring|what we.re looking for"
     r"|you.ll have|you (will )?have|must.have|we.re looking for|we want to hear)", "requirements"),
    (r"(?i)^(responsibilities?|primary (job )?duties?|what you.ll do|what you will do"
     r"|the role|about the role|your role|what will you do"
     r"|job responsibilities?|in this role|you will|key responsibilities?)", "responsibilities"),
    (r"(?i)^(nice.to.have|preferred|bonus|plus|good.to.have|added bonus)", "preferred"),
    (r"(?i)^(about us|about the company|who we are|company overview|our mission)", "about"),
    (r"(?i)^(benefits?|what we offer|perks|why work|compensation|why join)", "benefits"),
    (r"(?i)^(job requirements?|job responsibilities?|job description)", "meta"),
]

# ---- Tech keyword patterns for skill extraction -----------------------------
TECH_SKILL_PATTERNS = [
    # Data / Warehouse
    r"\bsql\b", r"\bpython\b", r"\bdbt\b", r"\bairflow\b", r"\bdagster\b",
    r"\bprefect\b", r"\bsnowflake\b", r"\bbigquery\b", r"\bredshift\b",
    r"\bspark\b", r"\bkafka\b", r"\bflink\b", r"\bhadoop\b",
    r"\belastic\b", r"\belasticsearch\b",
    # Cloud
    r"\baws\b", r"\bgcp\b", r"\bazure\b", r"\blambda\b", r"\bdynamodb\b",
    r"\bec2\b", r"\bs3\b", r"\beks\b", r"\beks\b", r"\bglue\b",
    r"\bkubernetes\b", r"\bk8s\b", r"\bdocker\b", r"\bterraform\b",
    r"\bansible\b", r"\bhelm\b",
    # CRM / SaaS
    r"\bsalesforce\b", r"\bhubspot\b", r"\bmarketo\b", r"\bworkday\b",
    r"\badp\b", r"\bnetsuite\b", r"\bquickbooks\b", r"\bstripe\b",
    r"\brippling\b", r"\bgusto\b", r"\bpaychex\b", r"\bsap\b",
    r"\bzendesk\b", r"\bintercom\b", r"\bfreshdesk\b",
    # Integration / API
    r"\brest api\b", r"\brest\b", r"\bgraphql\b", r"\bwebhook\b",
    r"\boauth\b", r"\bsaml\b", r"\bscim\b", r"\bsso\b", r"\bokta\b",
    r"\bauth0\b", r"\bfivetran\b", r"\bairbyte\b", r"\bstitch\b",
    r"\bworkato\b", r"\bzapier\b", r"\bboomi\b",
    # Languages
    r"\bjava\b", r"\bjava\b", r"\bjavascript\b", r"\btypescript\b",
    r"\bgo\b", r"\brust\b", r"\bscala\b", r"\bruby\b", r"\bphp\b",
    r"\bc\+\+\b", r"\b\.net\b", r"\br\b",
    # BI
    r"\blooker\b", r"\btableau\b", r"\bpower bi\b", r"\bmetabase\b",
    r"\bsisense\b", r"\bdomo\b", r"\bmicrostrategy\b", r"\bgrafana\b",
    r"\blookml\b",
    # Microsoft SQL Server stack (legacy enterprise)
    r"\bssis\b", r"\bssrs\b", r"\bssas\b", r"\bt-sql\b", r"\btsql\b",
    r"\bms sql\b", r"\bms sql server\b", r"\bsql server\b", r"\bssms\b",
    r"\bvisual studio\b", r"\bssdt\b", r"\bdynamic 365\b", r"\bpowerbi\b",
    # Databases
    r"\bpostgresql\b", r"\bpostgres\b", r"\bmysql\b", r"\bmongodb\b",
    r"\bcassandra\b", r"\bredis\b", r"\bneo4j\b", r"\bcosmosdb\b",
    r"\boracle\b", r"\bdb2\b", r"\bmariadb\b", r"\bsqlite\b",
    # DevOps / Engineering
    r"\bgit\b", r"\bgithub\b", r"\bci/cd\b", r"\bjenkins\b",
    r"\bcircleci\b", r"\bgitlab ci\b", r"\bjira\b", r"\bconfluence\b",
    r"\bnotion\b", r"\basana\b", r"\blinear\b",
    # AI / ML
    r"\bmachine learning\b", r"\bml\b", r"\bdeep learning\b",
    r"\bllm\b", r"\bai\b", r"\bnlp\b", r"\bmlops\b", r"\bmlflow\b",
]

# ---- High-signal JD keywords (non-tech) ------------------------------------
CONTEXT_KEYWORDS = [
    "implementation", "onboarding", "deployment", "integration", "pipeline",
    "data quality", "data engineer", "solutions engineer", "analytics engineer",
    "data warehouse", "data modeling", "etl", "elt", "data governance",
    "data catalog", "metadata", "lineage", "orchestration",
    "client-facing", "customer-facing", "post-sales", "pre-sales",
    "stakeholder", "cross-functional", "enterprise", "saas",
    "startup", "series a", "series b", "series c", "founding", "greenfield",
    "build from scratch", "first hire", "mission-driven",
    "healthcare", "fintech", "edtech", "hr tech", "regtech", "proptech",
    "revenue operations", "revops", "customer success",
    "scrum", "agile", "sprint", "kanban",
    "remote", "hybrid", "new york", "nyc",
]


def load_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def infer_company_role_from_filename(filename: str) -> tuple[str, str]:
    """Extract company and role from the archive filename convention.
    Expected: job-desc-{company}-{role}.txt
    """
    stem = Path(filename).stem
    # Strip leading 'job-desc-'
    slug = re.sub(r"^job-desc-", "", stem)
    parts = slug.split("-", 1)
    if len(parts) == 2:
        company = parts[0].replace("-", " ").title()
        role = parts[1].replace("-", " ").title()
    else:
        company = "Unknown"
        role = slug.replace("-", " ").title()
    return company, role


def detect_seniority(text: str) -> str:
    lower = text.lower()
    if any(w in lower for w in ["staff engineer", "principal", "director", "vp ", "head of", "vp,"]):
        return "senior+"
    elif any(w in lower for w in ["senior", "sr.", " sr ", "lead ", "manager", " ii", " iii"]):
        return "senior"
    elif any(w in lower for w in ["junior", "jr.", "entry level", "associate", "early career"]):
        return "junior"
    else:
        return "mid"


def split_into_sections(text: str) -> dict[str, list[str]]:
    """Split raw JD text into labeled sections using header heuristics."""
    sections: dict[str, list[str]] = {
        "requirements": [],
        "responsibilities": [],
        "preferred": [],
        "about": [],
        "benefits": [],
        "other": [],
    }
    current = "other"
    lines = text.splitlines()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Only test short lines as potential headers (headers rarely > 80 chars)
        if len(stripped) < 100:
            matched = False
            for pattern, section_key in SECTION_PATTERNS:
                if re.search(pattern, stripped):
                    current = section_key
                    matched = True
                    break
            if matched:
                continue  # Don't add the header itself as content

        sections[current].append(stripped)

    return sections


def extract_tech_skills(text: str) -> list[str]:
    """Return a deduplicated list of detected tech skill tokens."""
    found: set[str] = set()
    lower = text.lower()
    for pattern in TECH_SKILL_PATTERNS:
        match = re.search(pattern, lower)
        if match:
            found.add(match.group().strip())
    return sorted(found)


def extract_context_keywords(text: str) -> list[str]:
    """Return high-signal contextual keywords found in the JD."""
    lower = text.lower()
    return [kw for kw in CONTEXT_KEYWORDS if kw in lower]


def clean_bullets(lines: list[str], max_len: int = 250) -> list[str]:
    """Strip bullet markers and filter to sentence-like lines."""
    cleaned = []
    for line in lines:
        line = re.sub(r"^[•\-\*·▪→✓►]+\s*", "", line).strip()
        if 15 < len(line) < max_len:
            cleaned.append(line)
    return cleaned


def parse_jd(
    jd_path: Path,
    company_override: str | None = None,
    role_override: str | None = None,
) -> dict:
    text = load_text(jd_path)
    sections = split_into_sections(text)

    inferred_company, inferred_role = infer_company_role_from_filename(jd_path.name)
    company = company_override or inferred_company
    role = role_override or inferred_role

    # Title: first short non-empty line in 'other' or 'about', or inferred role
    title_candidate = role
    for line in sections.get("other", []) + sections.get("about", []):
        if 5 < len(line) < 80 and not line.lower().startswith("http"):
            title_candidate = line
            break

    req_text = "\n".join(sections["requirements"])
    pref_text = "\n".join(sections["preferred"])
    full_text = text

    req_skills = extract_tech_skills(req_text)
    pref_skills = [s for s in extract_tech_skills(pref_text) if s not in req_skills]
    all_skills = extract_tech_skills(full_text)
    # Skills in full text but not explicitly required/preferred
    other_skills = [s for s in all_skills if s not in req_skills and s not in pref_skills]

    responsibilities = clean_bullets(sections["responsibilities"])[:12]
    requirements_text = clean_bullets(sections["requirements"])[:15]

    raw_keywords = extract_context_keywords(full_text)

    return {
        "source_file": str(jd_path.name),
        "parsed_date": str(date.today()),
        "company": company,
        "inferred_role": role,
        "title_candidate": title_candidate,
        "seniority": detect_seniority(full_text),
        "required_skills": req_skills,
        "preferred_skills": pref_skills,
        "other_mentioned_skills": other_skills,
        "responsibilities": responsibilities,
        "requirements_text": requirements_text,
        "raw_keywords": raw_keywords,
        "full_text_length": len(full_text),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Parse a raw job description into structured YAML"
    )
    parser.add_argument("--job", required=True, help="Path to raw JD text file")
    parser.add_argument("--company", help="Override inferred company name")
    parser.add_argument("--role", help="Override inferred role name")
    parser.add_argument(
        "--output",
        help="Output path (default: archive/jd-parsed-{slug}-{date}.yaml)",
    )
    args = parser.parse_args()

    jd_path = Path(args.job)
    if not jd_path.exists():
        print(f"Error: JD file not found: {jd_path}")
        sys.exit(1)

    result = parse_jd(jd_path, args.company, args.role)

    if args.output:
        output_path = Path(args.output)
    else:
        slug = jd_path.stem.replace("job-desc-", "")
        output_path = ROOT / "archive" / f"jd-parsed-{slug}-{date.today()}.yaml"

    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(result, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"Parsed JD written to: {output_path}")
    print(f"  Company: {result['company']}")
    print(f"  Role: {result['inferred_role']}")
    print(f"  Seniority: {result['seniority']}")
    print(f"  Required skills detected: {len(result['required_skills'])}")
    print(f"  Keywords: {', '.join(result['raw_keywords'][:8])}")
    print(f"\nNext step: python scripts/scorer.py --jd {args.job} --parsed-jd {output_path}")

    return str(output_path)


if __name__ == "__main__":
    main()
