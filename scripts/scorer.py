#!/usr/bin/env python3
"""
JD Scorer — pre-scores a parsed job description against the skill taxonomy.

Loads skill-taxonomy.yaml and a parsed JD YAML (from jd_parser.py), then
builds a keyword index and scores each skill against JD mentions. Outputs
a ranked match YAML that generate_resume.py injects into prompts so the LLM
validates and refines rather than re-discovering scores from scratch.

Usage:
    python scripts/scorer.py --jd archive/job-desc-hibob.txt --parsed-jd archive/jd-parsed-hibob-2026-02-20.yaml
    python scripts/scorer.py --jd archive/job-desc-hibob.txt --parsed-jd archive/jd-parsed-hibob-2026-02-20.yaml --summary
    python scripts/scorer.py --jd archive/job-desc-hibob.txt --parsed-jd archive/jd-parsed-hibob-2026-02-20.yaml --output archive/jd-scores-hibob.yaml
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
TAXONOMY_PATH = ROOT / "portfolio" / "skill-taxonomy.yaml"


def load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _normalize(text: str) -> str:
    """Lowercase and collapse whitespace."""
    return re.sub(r"\s+", " ", text.lower().strip())


def _tokenize_skill_name(name: str) -> list[str]:
    """Split a skill name into searchable sub-tokens."""
    lower = name.lower()
    tokens = {lower}  # full name
    # Individual words
    for word in re.findall(r"[a-z][a-z0-9+#.]*", lower):
        if len(word) > 1:
            tokens.add(word)
    # Slash variants: "AWS Redshift / RDS" → "redshift", "rds"
    for part in re.split(r"[/,]", lower):
        part = part.strip()
        if part:
            tokens.add(part)
    return list(tokens)


def build_skill_index(taxonomy: dict) -> list[dict]:
    """Build a search index from skill-taxonomy.yaml."""
    index = []
    for cat in taxonomy.get("categories", []):
        for skill in cat.get("skills", []):
            name = skill.get("skill", "")
            if not name:
                continue

            evidence = [
                e for e in skill.get("evidence", [])
                if e and not str(e).startswith("#")
            ]
            aliases = skill.get("aliases", []) or []

            # Build search tokens: name variants + aliases + evidence nouns
            search_tokens: set[str] = set()
            for token in _tokenize_skill_name(name):
                search_tokens.add(token)
            for alias in aliases:
                search_tokens.update(_tokenize_skill_name(str(alias)))
            # Key nouns from first 3 evidence entries
            for ev in evidence[:3]:
                nouns = re.findall(r"\b[a-z][a-z0-9+#.]{2,}\b", _normalize(str(ev)))
                search_tokens.update(nouns[:8])

            index.append({
                "skill": name,
                "category": cat.get("category", ""),
                "proficiency": skill.get("proficiency", "unknown"),
                "years": skill.get("years", 0),
                "evidence": evidence[:3],
                "applicable_roles": skill.get("applicable_roles", []) or [],
                "search_tokens": list(search_tokens),
            })
    return index


def _count_hits(tokens: list[str], text: str) -> int:
    """Count total token occurrences in text (capped per token to avoid noise)."""
    total = 0
    for token in tokens:
        pattern = r"\b" + re.escape(token) + r"\b"
        count = len(re.findall(pattern, text))
        total += min(count, 3)  # cap each token at 3 to prevent one word dominating
    return total


def score_skill(entry: dict, jd_text_lower: str, req_text: str, pref_text: str, raw_kws: list[str]) -> dict:
    """Score a single skill against the JD."""
    tokens = entry["search_tokens"]

    required_hits = _count_hits(tokens, req_text)
    preferred_hits = _count_hits(tokens, pref_text)
    full_hits = _count_hits(tokens, jd_text_lower)

    # Check if skill name or close variant appears in raw_keywords list
    skill_lower = entry["skill"].lower()
    kw_bonus = sum(1 for kw in raw_kws if skill_lower in kw or kw in skill_lower)

    # Weighted raw score
    raw = (required_hits * 3.0) + (preferred_hits * 1.5) + (full_hits * 0.5) + (kw_bonus * 2.0)

    # Normalize to 0–10
    confidence = round(min(10.0, raw * 1.2), 1)

    if confidence >= 7:
        category = "STRONG_MATCH"
    elif confidence >= 4:
        category = "PARTIAL_MATCH"
    elif confidence >= 1:
        category = "WEAK_SIGNAL"
    else:
        category = "NOT_IN_JD"

    return {
        "skill": entry["skill"],
        "category": entry["category"],
        "proficiency": entry["proficiency"],
        "years": entry["years"],
        "jd_hits": full_hits,
        "confidence": confidence,
        "match_category": category,
        "evidence_summary": "; ".join(str(e) for e in entry["evidence"][:2]) if entry["evidence"] else "",
    }


def run_scoring(jd_path: Path, parsed_jd_path: Path, taxonomy: dict) -> tuple[list[dict], dict]:
    """Score all taxonomy skills and compute a summary."""
    jd_text = load_text(jd_path)
    parsed_jd = load_yaml(parsed_jd_path)

    jd_lower = _normalize(jd_text)
    req_text = _normalize(" ".join(parsed_jd.get("required_skills", [])))
    pref_text = _normalize(" ".join(parsed_jd.get("preferred_skills", [])))
    raw_kws = [_normalize(k) for k in parsed_jd.get("raw_keywords", [])]

    skill_index = build_skill_index(taxonomy)

    scores = [
        score_skill(entry, jd_lower, req_text, pref_text, raw_kws)
        for entry in skill_index
    ]
    scores.sort(key=lambda x: x["confidence"], reverse=True)

    summary = _compute_summary(scores, parsed_jd)
    return scores, summary


def _compute_summary(scores: list[dict], parsed_jd: dict) -> dict:
    strong = [s for s in scores if s["match_category"] == "STRONG_MATCH"]
    partial = [s for s in scores if s["match_category"] == "PARTIAL_MATCH"]
    weak = [s for s in scores if s["match_category"] == "WEAK_SIGNAL"]
    not_in = [s for s in scores if s["match_category"] == "NOT_IN_JD"]

    # Estimated fit: weighted average of top-10 confidence scores
    top10 = [s["confidence"] for s in scores[:10]]
    estimated = round(sum(top10) / len(top10), 1) if top10 else 0.0

    # Likely gaps = skills NOT in JD that we have at intermediate+ proficiency
    gap_levels = {"intermediate", "advanced", "expert"}
    likely_gaps = [
        s["skill"] for s in not_in
        if s.get("proficiency", "").lower() in gap_levels
    ][:6]

    return {
        "company": parsed_jd.get("company", ""),
        "inferred_role": parsed_jd.get("inferred_role", ""),
        "seniority": parsed_jd.get("seniority", ""),
        "estimated_fit_score": estimated,
        "strong_match_count": len(strong),
        "partial_match_count": len(partial),
        "weak_signal_count": len(weak),
        "not_in_jd_count": len(not_in),
        "top_matching_skills": [s["skill"] for s in strong[:8]],
        "partial_matching_skills": [s["skill"] for s in partial[:6]],
        "likely_gaps": likely_gaps,
    }


def print_summary(summary: dict) -> None:
    print("\n" + "=" * 55)
    print(f"  Pre-Score Summary: {summary.get('company')} — {summary.get('inferred_role')}")
    print("=" * 55)
    print(f"  Estimated fit score : {summary['estimated_fit_score']}/10")
    print(f"  Seniority signal    : {summary.get('seniority', 'unknown')}")
    print(f"  Strong matches      : {summary['strong_match_count']}")
    print(f"  Partial matches     : {summary['partial_match_count']}")
    print()
    if summary["top_matching_skills"]:
        print(f"  Top skills          : {', '.join(summary['top_matching_skills'][:6])}")
    if summary["partial_matching_skills"]:
        print(f"  Partial matches     : {', '.join(summary['partial_matching_skills'][:5])}")
    if summary["likely_gaps"]:
        print(f"  Likely gaps         : {', '.join(summary['likely_gaps'][:4])}")
    print("=" * 55 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Pre-score a parsed JD against the skill taxonomy"
    )
    parser.add_argument("--jd", required=True, help="Path to raw JD text file")
    parser.add_argument(
        "--parsed-jd", required=True, dest="parsed_jd",
        help="Path to parsed JD YAML (from jd_parser.py)"
    )
    parser.add_argument(
        "--output",
        help="Output path (default: archive/jd-scores-{slug}-{date}.yaml)"
    )
    parser.add_argument(
        "--summary", action="store_true",
        help="Print a human-readable summary to terminal"
    )
    args = parser.parse_args()

    taxonomy_path = TAXONOMY_PATH
    if not taxonomy_path.exists():
        print(f"Error: skill-taxonomy.yaml not found at {taxonomy_path}")
        sys.exit(1)

    taxonomy = load_yaml(taxonomy_path)
    jd_path = Path(args.jd)
    parsed_jd_path = Path(args.parsed_jd)

    if not jd_path.exists():
        print(f"Error: JD file not found: {jd_path}")
        sys.exit(1)
    if not parsed_jd_path.exists():
        print(f"Error: Parsed JD not found: {parsed_jd_path}")
        sys.exit(1)

    scores, summary = run_scoring(jd_path, parsed_jd_path, taxonomy)

    output_data = {
        "source_jd": str(jd_path.name),
        "parsed_jd": str(parsed_jd_path.name),
        "scored_date": str(date.today()),
        "summary": summary,
        "scores": scores,
    }

    if args.output:
        output_path = Path(args.output)
    else:
        slug = jd_path.stem.replace("job-desc-", "")
        output_path = ROOT / "archive" / f"jd-scores-{slug}-{date.today()}.yaml"

    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(output_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"Scores written to: {output_path}")

    if args.summary:
        print_summary(summary)
    else:
        print(
            f"  Estimated fit: {summary['estimated_fit_score']}/10  |  "
            f"Strong: {summary['strong_match_count']}  |  "
            f"Partial: {summary['partial_match_count']}"
        )
        print(f"\nNext step: python scripts/generate_resume.py --parsed-jd {parsed_jd_path} --pre-scores {output_path}")

    return str(output_path)


if __name__ == "__main__":
    main()
