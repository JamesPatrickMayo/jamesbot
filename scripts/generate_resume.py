#!/usr/bin/env python3
"""
Resume & Fit-Evaluation Prompt Assembler

Reads the skill taxonomy, master portfolio, role structure, and a target
job description, then assembles a complete LLM prompt for either resume
generation or fit evaluation. The prompt is written to output/ for use
with Cursor, ChatGPT, Claude, or any LLM.

Optional pre-computed context flags (from jd_parser.py + scorer.py) shift
the LLM from "discover + score + generate" to "validate + refine + generate,"
substantially reducing reasoning load and improving consistency.

Usage:
    # Basic (LLM does full analysis):
    python scripts/generate_resume.py \\
        --job archive/job-desc-hibob-cs-solution-architect.txt \\
        --role solutions-engineer

    # Enriched (LLM validates pre-computed analysis):
    python scripts/generate_resume.py \\
        --job archive/job-desc-hibob.txt \\
        --role solutions-engineer \\
        --parsed-jd archive/jd-parsed-hibob-2026-02-20.yaml \\
        --pre-scores archive/jd-scores-hibob-2026-02-20.yaml

    # Full pipeline with content banks:
    python scripts/generate_resume.py \\
        --job archive/job-desc-hibob.txt \\
        --role solutions-engineer \\
        --parsed-jd archive/jd-parsed-hibob-2026-02-20.yaml \\
        --pre-scores archive/jd-scores-hibob-2026-02-20.yaml \\
        --bullet-bank portfolio/bullet-bank.yaml \\
        --paragraph-bank portfolio/paragraph-bank.yaml

    # Fit evaluation:
    python scripts/generate_resume.py \\
        --job archive/job-desc-hibob.txt \\
        --role solutions-engineer \\
        --mode fit-eval

    # Cover letter using existing fit eval:
    python scripts/generate_resume.py \\
        --job archive/job-desc-hibob.txt \\
        --role solutions-engineer \\
        --mode cover-letter \\
        --fit-eval output/application-hibob-2026-02-20.md
"""

import argparse
import sys
from datetime import date
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)


ROOT = Path(__file__).resolve().parent.parent

PORTFOLIO_PATH = ROOT / "portfolio" / "master-portfolio.yaml"
TAXONOMY_PATH = ROOT / "portfolio" / "skill-taxonomy.yaml"
STANDARDS_PATH = ROOT / "templates" / "resume-standards.md"
FIT_EVAL_STRUCTURE_PATH = ROOT / "templates" / "fit-evaluation-structure.yaml"
COVER_LETTER_STRUCTURE_PATH = ROOT / "templates" / "cover-letter-structure.yaml"
STRUCTURES_DIR = ROOT / "templates" / "structures"
OUTPUT_DIR = ROOT / "output"

# Default content bank paths (used when --bullet-bank / --paragraph-bank not specified)
DEFAULT_BULLET_BANK = ROOT / "portfolio" / "bullet-bank.yaml"
DEFAULT_PARAGRAPH_BANK = ROOT / "portfolio" / "paragraph-bank.yaml"


def load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def get_available_roles() -> list[str]:
    return [p.stem for p in STRUCTURES_DIR.glob("*.yaml")]


# ---- Pre-computed context injection -----------------------------------------

def format_precomputed_context(parsed_jd: dict | None, scores: dict | None) -> str:
    """
    Format pre-parsed JD and pre-scored skills into a prompt prefix block.
    When present, this shifts the LLM from discovery mode to validation mode.
    """
    if not parsed_jd and not scores:
        return ""

    lines = [
        "## PRE-COMPUTED JD ANALYSIS",
        "IMPORTANT: The following analysis was pre-computed from the job description.",
        "Your task is to VALIDATE these results, adjust where the evidence warrants it,",
        "then generate the requested output. Do not re-derive from scratch.",
        "",
    ]

    if parsed_jd:
        lines += [
            f"**Company:** {parsed_jd.get('company', 'Unknown')}",
            f"**Role:** {parsed_jd.get('inferred_role', 'Unknown')}",
            f"**Seniority signal:** {parsed_jd.get('seniority', 'unknown')}",
        ]
        req = parsed_jd.get("required_skills", [])
        if req:
            lines.append(f"**Required skills detected:** {', '.join(req)}")
        pref = parsed_jd.get("preferred_skills", [])
        if pref:
            lines.append(f"**Preferred skills detected:** {', '.join(pref)}")
        kw = parsed_jd.get("raw_keywords", [])
        if kw:
            lines.append(f"**Key context keywords:** {', '.join(kw[:12])}")
        lines.append("")

    if scores:
        summary = scores.get("summary", {})
        lines += [
            f"**Estimated fit score (pre-computed):** {summary.get('estimated_fit_score', '?')}/10",
            f"**Strong skill matches:** {summary.get('strong_match_count', 0)}",
            f"**Partial matches:** {summary.get('partial_match_count', 0)}",
        ]
        top = summary.get("top_matching_skills", [])
        if top:
            lines.append(f"**Top matching skills:** {', '.join(top[:8])}")
        partial = summary.get("partial_matching_skills", [])
        if partial:
            lines.append(f"**Partial matching skills:** {', '.join(partial[:6])}")
        gaps = summary.get("likely_gaps", [])
        if gaps:
            lines.append(f"**Likely skill gaps:** {', '.join(gaps[:5])}")
        lines.append("")

        # Top scored skills detail table
        skill_scores = scores.get("scores", [])
        strong_scores = [s for s in skill_scores if s.get("match_category") == "STRONG_MATCH"]
        if strong_scores:
            lines.append("**Top pre-scored skill matches (validate and adjust):**")
            for s in strong_scores[:10]:
                ev = s.get("evidence_summary", "")
                ev_short = (ev[:80] + "…") if len(ev) > 80 else ev
                lines.append(
                    f"- {s['skill']} [{s['proficiency']}] — confidence {s['confidence']}/10 — {ev_short}"
                )
            lines.append("")

    lines.append("---")
    lines.append("")
    return "\n".join(lines)


# ---- Content bank helpers ---------------------------------------------------

def _slug(text: str) -> str:
    """Simple token normalizer for matching."""
    import re
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower()).strip()


def preselect_bullets(
    bullet_bank: dict,
    jd_keywords: list[str],
    role: str,
    max_per_company: int = 5,
) -> dict[str, list[dict]]:
    """
    Score each bullet in the bank against JD keywords and return the top N
    per company, keyed by company name.

    Returns: {"QuotaPath": [{"text": ..., "tags": [...], "clusters": [...]}, ...], ...}
    """
    kw_set = set(_slug(k) for k in jd_keywords)
    result: dict[str, list[dict]] = {}

    for entry in bullet_bank.get("companies", []):
        company = entry.get("company", "Unknown")
        bullets = entry.get("bullets", [])

        scored = []
        for b in bullets:
            tags = [_slug(t) for t in (b.get("tags") or [])]
            clusters = [_slug(c) for c in (b.get("clusters") or [])]
            roles = b.get("applicable_roles") or []

            # Score: tag/cluster overlap with JD keywords
            tag_hits = sum(1 for t in tags if any(t in kw or kw in t for kw in kw_set))
            cluster_hits = sum(1 for c in clusters if any(c in kw or kw in c for kw in kw_set))
            # Bonus if bullet is marked for this role
            role_bonus = 2 if not roles or role in roles else 0
            score = tag_hits * 2 + cluster_hits * 1.5 + role_bonus

            scored.append((score, b))

        # Sort descending, take top N
        scored.sort(key=lambda x: x[0], reverse=True)
        result[company] = [b for _, b in scored[:max_per_company]]

    return result


def preselect_paragraphs(
    paragraph_bank: dict,
    jd_keywords: list[str],
    role: str,
    max_paragraphs: int = 3,
) -> list[dict]:
    """
    Score cover letter paragraph blocks against JD keywords and return the top N.
    """
    kw_set = set(_slug(k) for k in jd_keywords)
    scored = []

    for para in paragraph_bank.get("paragraphs", []):
        tags = [_slug(t) for t in (para.get("tags") or [])]
        applicable = para.get("applicable_roles") or []

        tag_hits = sum(1 for t in tags if any(t in kw or kw in t for kw in kw_set))
        role_bonus = 2 if not applicable or role in applicable else 0
        score = tag_hits * 2 + role_bonus

        scored.append((score, para))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:max_paragraphs]]


def format_preselected_bullets(bullets_by_company: dict[str, list[dict]]) -> str:
    """Format pre-selected bullets for injection into the resume prompt."""
    if not bullets_by_company:
        return ""
    lines = [
        "## PRE-SELECTED BULLET BANK",
        "The following bullet variants were pre-scored against JD keywords.",
        "USE these as your primary source for resume bullets — reorder, tighten, or lightly",
        "rewrite for tone, but do NOT replace them with generic content.",
        "",
    ]
    for company, bullets in bullets_by_company.items():
        if not bullets:
            continue
        lines.append(f"### {company}")
        for b in bullets:
            tags = ", ".join(b.get("tags") or [])
            lines.append(f"- {b.get('text', '')}  _(tags: {tags})_")
        lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def format_preselected_paragraphs(paragraphs: list[dict]) -> str:
    """Format pre-selected cover letter paragraphs for injection."""
    if not paragraphs:
        return ""
    lines = [
        "## PRE-SELECTED COVER LETTER PARAGRAPHS",
        "Use these paragraph blocks as the basis for the cover letter.",
        "Stitch them together with natural transitions; adapt tone as needed.",
        "",
    ]
    for p in paragraphs:
        scenario = p.get("scenario", "")
        lines.append(f"### Scenario: {scenario}")
        lines.append(p.get("text", ""))
        lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def filter_taxonomy_for_role(taxonomy: dict, role: str) -> dict:
    """Return only skills applicable to the target role."""
    filtered = {"categories": []}
    for cat in taxonomy.get("categories", []):
        filtered_skills = [
            s for s in cat.get("skills", [])
            if role in s.get("applicable_roles", [])
        ]
        if filtered_skills:
            filtered["categories"].append({
                "category": cat["category"],
                "skills": filtered_skills,
            })
    return filtered


def filter_experience_for_role(portfolio: dict, structure: dict) -> list[dict]:
    """Annotate experience entries with priority themes from the role structure."""
    emphasis = structure.get("experience_bullet_emphasis", {})
    high = set(emphasis.get("high_priority_themes", []))
    medium = set(emphasis.get("medium_priority_themes", []))

    entries = []
    for exp in portfolio.get("experience", []):
        entry = dict(exp)
        entry["_priority_note"] = (
            f"HIGH priority themes for this role: {', '.join(high)}\n"
            f"MEDIUM priority themes: {', '.join(medium)}"
        )
        entries.append(entry)
    return entries


def format_candidate_data(
    portfolio: dict,
    taxonomy: dict,
    structure: dict,
    role: str,
) -> str:
    """Format the candidate's data block shared by both prompt types."""
    filtered_tax = filter_taxonomy_for_role(taxonomy, role)
    annotated_exp = filter_experience_for_role(portfolio, structure)

    block = f"""## CANDIDATE — PERSONAL INFO
Name: {portfolio.get('personal', {}).get('name', 'James Mayo')}
Location: {portfolio.get('personal', {}).get('location', 'New York, NY')}
Email: {portfolio.get('personal', {}).get('email', '')}
LinkedIn: {portfolio.get('personal', {}).get('linkedin', '')}

## CANDIDATE — SUMMARY DATABASE
Core: {portfolio.get('summary', {}).get('core', '')}
Specializations: {', '.join(portfolio.get('summary', {}).get('specializations', []))}
Secondary strengths: {', '.join(portfolio.get('summary', {}).get('secondary_strengths', []))}

## CANDIDATE — FULL SKILL TAXONOMY (all skills, with proficiency and evidence)
"""
    for cat in taxonomy.get("categories", []):
        block += f"\n### {cat['category']}\n"
        for s in cat["skills"]:
            evidence_str = "; ".join(
                e for e in s.get("evidence", []) if e and not e.startswith("# TODO")
            )
            roles_str = ", ".join(s.get("applicable_roles", []))
            block += (
                f"- {s['skill']} [{s['proficiency']}] ({s.get('years', '?')}yr) "
                f"[roles: {roles_str}]: {evidence_str}\n"
            )

    block += f"\n## CANDIDATE — FILTERED SKILL TAXONOMY (skills applicable to {role})\n"
    for cat in filtered_tax.get("categories", []):
        block += f"\n### {cat['category']}\n"
        for s in cat["skills"]:
            evidence_str = "; ".join(
                e for e in s.get("evidence", []) if e and not e.startswith("# TODO")
            )
            block += (
                f"- {s['skill']} [{s['proficiency']}] ({s.get('years', '?')}yr): "
                f"{evidence_str}\n"
            )

    block += "\n## CANDIDATE — EXPERIENCE\n"
    for exp in annotated_exp:
        block += f"\n### {exp.get('title', '')} @ {exp.get('company', '')}\n"
        block += f"Dates: {exp.get('dates', '')}\n"
        env = exp.get('environment', [])
        if env:
            block += f"Environment: {', '.join(str(e) for e in env)}\n"
        block += f"Priority guidance: {exp.get('_priority_note', '')}\n"
        if exp.get('title_progression'):
            block += f"Progression: {exp['title_progression']}\n"
        if exp.get('direct_reports'):
            block += f"Direct reports: {exp['direct_reports']}\n"
        block += "Responsibilities:\n"
        for r in exp.get("responsibilities", []):
            block += f"  - {r}\n"
        metrics = exp.get("impact_metrics", {})
        if metrics:
            filled_metrics = {k: v for k, v in metrics.items() if v is not None}
            if filled_metrics:
                block += "Impact metrics:\n"
                for k, v in filled_metrics.items():
                    block += f"  - {k}: {v}\n"
        confirmed = exp.get("confirmed_contributions", [])
        if confirmed:
            block += "Confirmed contributions:\n"
            for c in confirmed:
                block += f"  - {c}\n"

    projects = portfolio.get("projects", [])
    if projects:
        block += "\n## CANDIDATE — PROJECTS\n"
        for p in projects:
            block += f"\n### {p.get('name', '')}\n"
            for c in p.get("contributions", []):
                block += f"  - {c}\n"

    education = portfolio.get("education", [])
    if education:
        block += "\n## CANDIDATE — EDUCATION\n"
        for e in education:
            if isinstance(e, dict):
                block += f"- {e.get('degree', '')} — {e.get('institution', '')} ({e.get('year', '')})\n"

    leadership = portfolio.get("leadership", {})
    if leadership:
        block += "\n## CANDIDATE — LEADERSHIP & COMMUNITY\n"
        for v in leadership.get("volunteer", []):
            note = f" — {v['note']}" if v.get('note') else ""
            block += f"- {v.get('organization', '')}: {v.get('role', '')}{note}\n"
        for m in leadership.get("confirmed_mentorship", []):
            block += f"- {m}\n"

    return block


def assemble_resume_prompt(
    job_text: str,
    role: str,
    portfolio: dict,
    taxonomy: dict,
    structure: dict,
    standards: str,
    precomputed_block: str = "",
    bullet_block: str = "",
) -> str:
    """Build the full LLM prompt for resume generation."""
    role_keywords = structure.get("keyword_targets", {})
    summary_focus = structure.get("summary_focus", {})

    bullet_instruction = (
        "4. For each role, PRIORITIZE bullets from the PRE-SELECTED BULLET BANK above. "
        "Reorder by relevance, tighten wording, mirror JD keywords. Do not swap them out for "
        "generic rewrites unless evidence is weak."
    ) if bullet_block else (
        "4. For each role, pick 3-5 bullets that best match the job. Rewrite them to:\n"
        "   - Lead with strong action verbs\n"
        "   - Include metrics where available\n"
        "   - Mirror the job description's keywords naturally"
    )

    prompt = f"""You are a resume generation assistant. Produce a tailored, ATS-optimized,
one-page resume in Markdown format.

{precomputed_block}{bullet_block}## TARGET JOB DESCRIPTION
{job_text}

## ROLE STRUCTURE: {structure.get('role_name', role)}
Summary focus: {summary_focus.get('identity', '')} — {summary_focus.get('tone', '')}
Emphasis areas: {', '.join(summary_focus.get('emphasis', []))}
Section order: {', '.join(structure.get('section_order', []))}

### Keyword Targets
Must include: {', '.join(role_keywords.get('must_include', []))}
Should include: {', '.join(role_keywords.get('should_include', []))}
Nice to have: {', '.join(role_keywords.get('nice_to_have', []))}

{format_candidate_data(portfolio, taxonomy, structure, role)}

## RESUME FORMATTING STANDARDS
{standards}

## OUTPUT INSTRUCTIONS
1. Generate a complete one-page resume in Markdown.
2. Write a custom 2-3 sentence summary tailored to the job description.
3. Select and order technical skills by relevance to this specific job.
{bullet_instruction}
5. After the resume, include a <!-- GENERATION NOTES --> block with:
   - Gap analysis: skills the job wants that are missing or weak
   - Confidence score (1-10)
   - Cover letter talking points
6. Do NOT fabricate experience or metrics.
7. Do NOT use first person.
"""
    return prompt


def assemble_fit_eval_prompt(
    job_text: str,
    role: str,
    portfolio: dict,
    taxonomy: dict,
    structure: dict,
    fit_eval_structure: dict,
    precomputed_block: str = "",
) -> str:
    """Build the full LLM prompt for fit evaluation."""
    sections = fit_eval_structure.get("sections", [])
    sections_block = ""
    for sec in sections:
        sections_block += f"\n### {sec['name']}\n"
        sections_block += f"{sec.get('description', '')}\n"
        if sec.get("fields"):
            for field in sec["fields"]:
                sections_block += f"- **{field['name']}**: {field.get('description', '')}\n"

    precomputed_note = (
        "The PRE-COMPUTED JD ANALYSIS above provides initial scores. "
        "Validate each score against the full evidence — adjust up or down as warranted. "
        "Do not simply echo these scores; your job is to stress-test them.\n\n"
    ) if precomputed_block else ""

    prompt = f"""You are a job fit evaluation assistant. Your task is to produce a thorough,
honest, structured fit evaluation comparing a candidate's skills and experience
against a specific job description.

Be rigorous. Flag real gaps. Do not inflate the candidate's fit. The candidate
uses this evaluation to decide whether to invest time applying.

{precomputed_block}## TARGET JOB DESCRIPTION
{job_text}

## CLOSEST ROLE STRUCTURE USED FOR FILTERING: {structure.get('role_name', role)}

{format_candidate_data(portfolio, taxonomy, structure, role)}

## FIT EVALUATION OUTPUT STRUCTURE

{precomputed_note}Produce the evaluation following this exact structure:
{sections_block}

## EVALUATION RULES
1. Be honest and specific. Do not inflate fit.
2. For each job requirement, cite specific evidence from the candidate's experience or mark as GAP.
3. Rate proficiency matches using the taxonomy's own levels (expert/advanced/intermediate/foundational).
4. When identifying gaps, suggest concrete mitigation strategies (reframe, learn, address in cover letter).
5. The overall fit score should reflect realistic interview success probability, not just keyword overlap.
6. Consider domain experience gaps separately from transferable skills.
7. Flag any red flags in the JD that might indicate poor culture fit or unrealistic expectations.
"""
    return prompt


def assemble_cover_letter_prompt(
    job_text: str,
    role: str,
    portfolio: dict,
    taxonomy: dict,
    structure: dict,
    cover_letter_structure: dict,
    fit_eval_text: str | None = None,
    precomputed_block: str = "",
    paragraph_block: str = "",
) -> str:
    """Build the full LLM prompt for cover letter generation."""
    cl_format = cover_letter_structure.get("format", {})
    sections = cover_letter_structure.get("sections", [])
    constraints = cover_letter_structure.get("constraints", [])

    sections_block = ""
    for sec in sections:
        sections_block += f"\n### {sec['name']}\n"
        sections_block += f"{sec.get('description', '')}\n"
        if sec.get("guidance"):
            for g in sec["guidance"]:
                sections_block += f"- {g}\n"

    constraints_block = "\n".join(f"- {c}" for c in constraints)

    fit_eval_block = ""
    if fit_eval_text:
        fit_eval_block = f"""
## FIT EVALUATION (use this to inform positioning and gap acknowledgment)
{fit_eval_text}
"""

    paragraph_instruction = (
        "Use the PRE-SELECTED COVER LETTER PARAGRAPHS above as your primary source material. "
        "Connect them with natural transitions and adapt tone to the specific company voice."
    ) if paragraph_block else (
        "Write naturally and specifically. Reference real accomplishments from the candidate data."
    )

    prompt = f"""You are a cover letter writing assistant. Write a tailored, compelling
cover letter for a specific job application.

The letter should sound like a real person — direct, confident, conversational.
Not corporate boilerplate. Not a template with blanks filled in.

{precomputed_block}{paragraph_block}## FORMAT
- Length: {cl_format.get('length', '3-4 paragraphs, 250-400 words')}
- Tone: {cl_format.get('tone', 'Professional but conversational')}
- Perspective: {cl_format.get('perspective', 'First person')}
- Address: {cl_format.get('address', 'Hiring Manager')}

## TARGET JOB DESCRIPTION
{job_text}

## CLOSEST ROLE STRUCTURE: {structure.get('role_name', role)}

{format_candidate_data(portfolio, taxonomy, structure, role)}
{fit_eval_block}
## COVER LETTER STRUCTURE

{paragraph_instruction}

Follow this structure:
{sections_block}

## CONSTRAINTS
{constraints_block}

## OUTPUT INSTRUCTIONS
1. Write the cover letter in Markdown, ready to copy-paste.
2. Do NOT include a subject line or email headers — just the letter body.
3. Start with "Dear Hiring Manager," (or specific name if provided in the JD).
4. End with "Best regards,\\nJames Mayo"
5. After the letter, include a <!-- GENERATION NOTES --> block with:
   - Which accomplishments were highlighted and why
   - Which gaps were addressed (if any)
   - Alternative angles that could be explored if this version doesn't land
"""
    return prompt


def main():
    parser = argparse.ArgumentParser(
        description="Assemble LLM prompts for resume generation, fit evaluation, or cover letter"
    )
    parser.add_argument(
        "--job", required=True, help="Path to the job description text file"
    )
    parser.add_argument(
        "--role",
        required=True,
        choices=get_available_roles(),
        help="Target role structure to use",
    )
    parser.add_argument(
        "--mode",
        choices=["resume", "fit-eval", "cover-letter"],
        default="resume",
        help="Prompt type: 'resume' (default), 'fit-eval', or 'cover-letter'",
    )
    parser.add_argument(
        "--fit-eval",
        dest="fit_eval_path",
        help="Path to an existing fit evaluation file (used by cover-letter mode)",
    )
    parser.add_argument(
        "--output",
        help="Output file path (default: output/prompt-{mode}-{role}-{date}.md)",
    )
    # --- Pre-computed context flags (Phase 1) ---
    parser.add_argument(
        "--parsed-jd",
        dest="parsed_jd",
        help="Path to parsed JD YAML from jd_parser.py (injects pre-computed structure)",
    )
    parser.add_argument(
        "--pre-scores",
        dest="pre_scores",
        help="Path to pre-scored skills YAML from scorer.py (injects ranked match table)",
    )
    # --- Content bank flags (Phase 2) ---
    parser.add_argument(
        "--bullet-bank",
        dest="bullet_bank",
        nargs="?",
        const=str(DEFAULT_BULLET_BANK),
        help="Path to bullet-bank.yaml (default: portfolio/bullet-bank.yaml). "
             "Pass flag with no value to use default path.",
    )
    parser.add_argument(
        "--paragraph-bank",
        dest="paragraph_bank",
        nargs="?",
        const=str(DEFAULT_PARAGRAPH_BANK),
        help="Path to paragraph-bank.yaml (default: portfolio/paragraph-bank.yaml). "
             "Pass flag with no value to use default path.",
    )
    args = parser.parse_args()

    portfolio = load_yaml(PORTFOLIO_PATH)
    taxonomy = load_yaml(TAXONOMY_PATH)
    structure = load_yaml(STRUCTURES_DIR / f"{args.role}.yaml")
    job_text = load_text(Path(args.job))

    # ---- Load optional pre-computed context ---------------------------------
    parsed_jd = None
    if args.parsed_jd:
        pjd_path = Path(args.parsed_jd)
        if pjd_path.exists():
            parsed_jd = load_yaml(pjd_path)
            print(f"  [+] Loaded parsed JD: {pjd_path.name}")
        else:
            print(f"  [!] Warning: --parsed-jd file not found: {args.parsed_jd}")

    pre_scores = None
    if args.pre_scores:
        ps_path = Path(args.pre_scores)
        if ps_path.exists():
            pre_scores = load_yaml(ps_path)
            print(f"  [+] Loaded pre-scores: {ps_path.name}")
        else:
            print(f"  [!] Warning: --pre-scores file not found: {args.pre_scores}")

    precomputed_block = format_precomputed_context(parsed_jd, pre_scores)

    # ---- Load optional content banks ----------------------------------------
    bullet_block = ""
    paragraph_block = ""
    jd_keywords = (parsed_jd or {}).get("raw_keywords", []) + (parsed_jd or {}).get("required_skills", [])

    if args.bullet_bank:
        bb_path = Path(args.bullet_bank)
        if bb_path.exists():
            bullet_bank = load_yaml(bb_path)
            bullets_by_company = preselect_bullets(bullet_bank, jd_keywords, args.role)
            bullet_block = format_preselected_bullets(bullets_by_company)
            total = sum(len(v) for v in bullets_by_company.values())
            print(f"  [+] Pre-selected {total} bullets from bullet bank")
        else:
            print(f"  [!] Warning: --bullet-bank file not found: {args.bullet_bank}")

    if args.paragraph_bank:
        pb_path = Path(args.paragraph_bank)
        if pb_path.exists():
            paragraph_bank = load_yaml(pb_path)
            paragraphs = preselect_paragraphs(paragraph_bank, jd_keywords, args.role)
            paragraph_block = format_preselected_paragraphs(paragraphs)
            print(f"  [+] Pre-selected {len(paragraphs)} cover letter paragraphs")
        else:
            print(f"  [!] Warning: --paragraph-bank file not found: {args.paragraph_bank}")

    # ---- Assemble prompt ----------------------------------------------------
    if args.mode == "resume":
        standards = load_text(STANDARDS_PATH)
        prompt = assemble_resume_prompt(
            job_text=job_text,
            role=args.role,
            portfolio=portfolio,
            taxonomy=taxonomy,
            structure=structure,
            standards=standards,
            precomputed_block=precomputed_block,
            bullet_block=bullet_block,
        )
    elif args.mode == "fit-eval":
        fit_eval_structure = load_yaml(FIT_EVAL_STRUCTURE_PATH)
        prompt = assemble_fit_eval_prompt(
            job_text=job_text,
            role=args.role,
            portfolio=portfolio,
            taxonomy=taxonomy,
            structure=structure,
            fit_eval_structure=fit_eval_structure,
            precomputed_block=precomputed_block,
        )
    else:
        cover_letter_structure = load_yaml(COVER_LETTER_STRUCTURE_PATH)
        fit_eval_text = None
        if args.fit_eval_path:
            fit_eval_text = load_text(Path(args.fit_eval_path))
        prompt = assemble_cover_letter_prompt(
            job_text=job_text,
            role=args.role,
            portfolio=portfolio,
            taxonomy=taxonomy,
            structure=structure,
            cover_letter_structure=cover_letter_structure,
            fit_eval_text=fit_eval_text,
            precomputed_block=precomputed_block,
            paragraph_block=paragraph_block,
        )

    OUTPUT_DIR.mkdir(exist_ok=True)
    output_path = args.output or str(
        OUTPUT_DIR / f"prompt-{args.mode}-{args.role}-{date.today().isoformat()}.md"
    )
    Path(output_path).write_text(prompt, encoding="utf-8")
    print(f"Prompt written to: {output_path}")
    print(f"Length: {len(prompt):,} characters")
    if precomputed_block:
        print("  [enriched mode] Pre-computed context injected — LLM will validate, not re-derive.")


if __name__ == "__main__":
    main()
