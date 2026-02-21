#!/usr/bin/env python3
"""
Resume & Fit-Evaluation Prompt Assembler

Reads the skill taxonomy, master portfolio, role structure, and a target
job description, then assembles a complete LLM prompt for either resume
generation or fit evaluation. The prompt is written to output/ for use
with Cursor, ChatGPT, Claude, or any LLM.

Usage:
    # Assemble a resume prompt:
    python scripts/generate_resume.py \
        --job archive/job-desc-hibob-cs-solution-architect.txt \
        --role solutions-engineer

    # Assemble a fit-evaluation prompt:
    python scripts/generate_resume.py \
        --job archive/job-desc-hibob-cs-solution-architect.txt \
        --role solutions-engineer \
        --mode fit-eval

    # Custom output path:
    python scripts/generate_resume.py \
        --job archive/job-desc-hibob-cs-solution-architect.txt \
        --role solutions-engineer \
        --output output/my-custom-prompt.md
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


def load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def get_available_roles() -> list[str]:
    return [p.stem for p in STRUCTURES_DIR.glob("*.yaml")]


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
) -> str:
    """Build the full LLM prompt for resume generation."""
    role_keywords = structure.get("keyword_targets", {})
    summary_focus = structure.get("summary_focus", {})

    prompt = f"""You are a resume generation assistant. Produce a tailored, ATS-optimized,
one-page resume in Markdown format.

## TARGET JOB DESCRIPTION
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
4. For each role, pick 3-5 bullets that best match the job. Rewrite them to:
   - Lead with strong action verbs
   - Include metrics where available
   - Mirror the job description's keywords naturally
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

    prompt = f"""You are a job fit evaluation assistant. Your task is to produce a thorough,
honest, structured fit evaluation comparing a candidate's skills and experience
against a specific job description.

Be rigorous. Flag real gaps. Do not inflate the candidate's fit. The candidate
uses this evaluation to decide whether to invest time applying.

## TARGET JOB DESCRIPTION
{job_text}

## CLOSEST ROLE STRUCTURE USED FOR FILTERING: {structure.get('role_name', role)}

{format_candidate_data(portfolio, taxonomy, structure, role)}

## FIT EVALUATION OUTPUT STRUCTURE

Produce the evaluation following this exact structure:
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

    prompt = f"""You are a cover letter writing assistant. Write a tailored, compelling
cover letter for a specific job application.

The letter should sound like a real person — direct, confident, conversational.
Not corporate boilerplate. Not a template with blanks filled in.

## FORMAT
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
        help="Path to an existing fit evaluation file (used by cover-letter mode)",
    )
    parser.add_argument(
        "--output",
        help="Output file path (default: output/prompt-{mode}-{role}-{date}.md)",
    )
    args = parser.parse_args()

    portfolio = load_yaml(PORTFOLIO_PATH)
    taxonomy = load_yaml(TAXONOMY_PATH)
    structure = load_yaml(STRUCTURES_DIR / f"{args.role}.yaml")
    job_text = load_text(Path(args.job))

    if args.mode == "resume":
        standards = load_text(STANDARDS_PATH)
        prompt = assemble_resume_prompt(
            job_text=job_text,
            role=args.role,
            portfolio=portfolio,
            taxonomy=taxonomy,
            structure=structure,
            standards=standards,
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
        )
    else:
        cover_letter_structure = load_yaml(COVER_LETTER_STRUCTURE_PATH)
        fit_eval_text = None
        if args.fit_eval:
            fit_eval_text = load_text(Path(args.fit_eval))
        prompt = assemble_cover_letter_prompt(
            job_text=job_text,
            role=args.role,
            portfolio=portfolio,
            taxonomy=taxonomy,
            structure=structure,
            cover_letter_structure=cover_letter_structure,
            fit_eval_text=fit_eval_text,
        )

    OUTPUT_DIR.mkdir(exist_ok=True)
    output_path = args.output or str(
        OUTPUT_DIR / f"prompt-{args.mode}-{args.role}-{date.today().isoformat()}.md"
    )
    Path(output_path).write_text(prompt, encoding="utf-8")
    print(f"Prompt written to: {output_path}")
    print(f"Length: {len(prompt):,} characters")


if __name__ == "__main__":
    main()
