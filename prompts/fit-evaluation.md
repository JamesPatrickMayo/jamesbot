# Fit Evaluation — LLM Prompt Template

Use this prompt with Cursor, ChatGPT, or Claude to generate a structured
job fit evaluation before investing time in a resume or application.

---

## Cursor Workflow (Recommended)

### Option 1: Use the Python assembler

```bash
python scripts/generate_resume.py --job archive/job-desc-[filename].txt --role [role] --mode fit-eval
```

Then ask Cursor to:

> Read `output/prompt-fit-eval-[role]-[date].md` and execute the instructions in it.
> Write the evaluation to `output/fit-eval-[company]-[role]-[date].md`.

### Option 2: Ask Cursor directly

> Evaluate my fit for this job. Read the job description from `archive/job-desc-[filename].txt`.
> Use the skill taxonomy from `portfolio/skill-taxonomy.yaml`, the master portfolio from
> `portfolio/master-portfolio.yaml`, and the fit evaluation structure from
> `templates/fit-evaluation-structure.yaml`.
> Use `templates/structures/[role].yaml` as the closest role structure.
> Output the evaluation to `output/fit-eval-[company]-[role]-[date].md`.

---

## Evaluation Structure (from `templates/fit-evaluation-structure.yaml`)

1. **Job Analysis** — Extract requirements, keywords, seniority, domain context
2. **Skill Match Matrix** — For each requirement: STRONG MATCH / PARTIAL MATCH / GAP
3. **Experience Relevance** — Score each role: HIGH / MEDIUM / LOW
4. **Overall Fit Score** — 1-10 composite with category breakdown
5. **Gap Analysis** — Missing skills with severity and mitigation strategies
6. **Positioning Strategy** — How to frame experience for this specific role
7. **Red Flags** — JD concerns and candidate weaknesses for this role
8. **Application Recommendation** — APPLY / APPLY WITH CAVEATS / SKIP

---

## Example Output Location

```
output/fit-eval-hibob-cs-solution-architect-2026-02-20.md
```
