# Cover Letter Generator — LLM Prompt Template

Use this prompt with Cursor, ChatGPT, or Claude to generate a tailored cover letter.
The cover letter should be generated *after* the fit evaluation, so the positioning
strategy and gap analysis can inform the narrative.

---

## Cursor Workflow (Recommended)

### Option 1: Use the Python assembler

```bash
python scripts/generate_resume.py --job archive/job-desc-[filename].txt --role [role] --mode cover-letter
```

Then ask Cursor to:

> Read `output/prompt-cover-letter-[role]-[date].md` and execute the instructions.
> Write the cover letter to `output/cover-letter-[company]-[role]-[date].md`.

### Option 2: Ask Cursor directly

> Generate a cover letter for this job. Read the job description from `archive/job-desc-[filename].txt`.
> Use the skill taxonomy from `portfolio/skill-taxonomy.yaml`, the master portfolio from
> `portfolio/master-portfolio.yaml`, the cover letter structure from
> `templates/cover-letter-structure.yaml`, and the fit evaluation from
> `output/fit-eval-[company]-[role]-[date].md` (if it exists).
> Output the cover letter to `output/cover-letter-[company]-[role]-[date].md`.

---

## Cover Letter Structure (from `templates/cover-letter-structure.yaml`)

1. **Opening Hook** — Name the role, express genuine interest, lead with strongest match
2. **Value Proposition** — 2-3 evidence-backed accomplishments mapped to JD requirements
3. **Gap Acknowledgment** (if applicable) — Address critical gaps head-on, pivot to strengths
4. **Closing & Call to Action** — Reiterate interest, express eagerness, close warmly

## Style Notes

The cover letter should:
- Sound like a real person, not a template
- Be direct and confident, not stiff or corporate
- Add narrative context the resume can't convey
- Use concrete metrics and specific examples
- Mirror JD language naturally without keyword stuffing
- Be 250-400 words (3-4 paragraphs)

---

## Example Output Location

```
output/cover-letter-hibob-cs-solution-architect-2026-02-20.md
```
