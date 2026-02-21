# Resume Generator — LLM Prompt Template

Use this prompt with Cursor, ChatGPT, or Claude to generate a tailored resume.

---

## Cursor Workflow (Recommended)

### Option 1: Use the Python assembler

The script reads all YAML data files, filters skills for the target role, and writes
a complete prompt to `output/`:

```bash
python scripts/generate_resume.py --job archive/job-desc-[filename].txt --role [role]
```

Then open the generated prompt file and paste it into Cursor chat, or ask Cursor to:

> Read `output/prompt-resume-[role]-[date].md` and execute the instructions in it.
> Write the resulting resume to `output/resume-[company]-[role]-[date].md`.

### Option 2: Ask Cursor directly

> Generate a resume for this job. Read the job description from `archive/job-desc-[filename].txt`.
> Use the skill taxonomy from `portfolio/skill-taxonomy.yaml`, the master portfolio from
> `portfolio/master-portfolio.yaml`, the resume standards from `templates/resume-standards.md`,
> and the role structure from `templates/structures/[role].yaml`.
> Output the resume to `output/resume-[company]-[role]-[date].md`.

---

## Prompt Structure (for reference)

The assembled prompt includes:
1. System instruction (resume generation assistant)
2. Full job description
3. Role structure (section order, keyword targets, emphasis areas)
4. Candidate personal info
5. Summary database
6. Full skill taxonomy with proficiency levels and evidence
7. Filtered skill taxonomy (role-specific subset)
8. Complete experience with responsibilities, metrics, and priority guidance
9. Projects, education, and leadership
10. Resume formatting standards
11. Output instructions with gap analysis

### Constraints
- Do NOT fabricate experience or metrics
- Do NOT include skills below "foundational" proficiency
- Do NOT exceed one page unless the role structure specifies otherwise
- Do NOT use first person ("I built...") — use implied first person ("Built...")
- Preserve factual accuracy from the master portfolio

---

## Example Output Location

```
output/resume-hibob-cs-solution-architect-2026-02-20.md
```
