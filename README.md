# JamesBot — Resume & Application Generation System

A structured, maintainable system that uses a canonical skills database to produce
targeted resumes, fit evaluations, and cover letters for specific job applications.

## Architecture

```
jamesbot/
├── portfolio/                        # Canonical skills database
│   ├── master-portfolio.yaml         # Full career history, responsibilities, impact metrics
│   ├── skill-taxonomy.yaml           # Normalized: role → skill → proficiency → evidence
│   ├── questionnaire.yaml            # Expansion questions + responses
│   ├── skill-development.yaml        # Skill gaps, learning roadmap, interview prep, resources
│   └── audit-2026-02-20.md           # Legitimacy sweep & cross-reference audit
│
├── templates/                        # Format definitions & reusable schemas
│   ├── resume-standards.md           # Global resume formatting rules and conventions
│   ├── fit-evaluation-structure.yaml # Reusable fit evaluation schema (8 sections)
│   ├── cover-letter-structure.yaml   # Cover letter generation schema
│   ├── linkedin-optimization.yaml   # LinkedIn profile section-by-section recommendations
│   └── structures/                   # Role-specific resume structures
│       ├── data-engineer.yaml
│       ├── analytics-engineer.yaml
│       ├── solutions-engineer.yaml
│       └── platform-architect.yaml
│
├── prompts/                          # LLM prompt templates
│   ├── resume-generator.md           # Resume generation prompt + Cursor workflow
│   ├── fit-evaluation.md             # Fit evaluation prompt + Cursor workflow
│   └── cover-letter.md               # Cover letter prompt + Cursor workflow
│
├── archive/                          # Unstructured source material
│   ├── job-desc-*.txt                # Saved job descriptions (one per application)
│   ├── *.pdf                         # Old resumes, cover letters, portfolio docs
│   └── *.csv                         # Interview prep notes, skill archives
│
├── job-search/                       # Job search strategy & tracking
│   ├── career-strategy.yaml          # Central career strategy (identity, dual-track, decisions)
│   └── search-strategy.yaml          # Search queries, recommended titles, sites
│
├── output/                           # Generated artifacts (gitignored)
│   ├── application-*.md              # Consolidated per-job files (fit eval + resume + cover letter)
│   └── prompt-*.md                   # Assembled LLM prompts (intermediate artifacts)
│
├── scripts/
│   └── generate_resume.py            # Prompt assembly orchestrator (resume, fit-eval, cover-letter)
│
└── .cursor/rules/
    └── resume-system.mdc             # Cursor rules for maintaining this system
```

## Workflow

### For Each Job Application

1. **Save** the job description to `archive/job-desc-{company}-{role}.txt`
2. **Ask Cursor** to evaluate and (if qualified) generate a full application:
   > Evaluate my fit for this job at `archive/job-desc-{company}-{role}.txt`.
   > If the fit score is 7.5/10 or higher, also generate a resume and cover letter.
   > Write everything to a single file: `output/application-{company}-{role}-{date}.md`.
3. **Review the output:**
   - If score < 7.5: file contains fit evaluation only, with a SKIP recommendation
   - If score >= 7.5: file contains fit evaluation + tailored resume + cover letter
4. **Iterate** — provide feedback on tone, style, and content

### Batch Processing

You can also provide multiple job URLs/descriptions at once. Cursor will:
1. Fetch and save all JDs to `archive/`
2. Run fit evaluations on all jobs
3. Only generate full applications (resume + cover letter) for jobs scoring 7.5+
4. Output one consolidated `application-*.md` file per job

### Using the Python Script (Optional)

The script assembles LLM prompts from YAML data files — useful if you want to use
the prompts outside of Cursor:

```bash
python scripts/generate_resume.py --job archive/job-desc-{company}-{role}.txt --role {closest-role} --mode fit-eval
python scripts/generate_resume.py --job archive/job-desc-{company}-{role}.txt --role {closest-role} --mode resume
python scripts/generate_resume.py --job archive/job-desc-{company}-{role}.txt --role {closest-role} --mode cover-letter
```

### Ongoing Maintenance

- When you gain new skills or complete projects, update `skill-taxonomy.yaml` first
- When you change jobs, update `master-portfolio.yaml`
- Periodically review `questionnaire.yaml` for unanswered expansion prompts
- Review and update `job-search/search-strategy.yaml` for new titles and sites
- Run periodic audits (see `portfolio/audit-*.md`) to verify taxonomy accuracy
- See `.cursor/rules/resume-system.mdc` for Cursor-specific conventions

## Key Concepts

- **Skill Taxonomy** — Normalized table mapping each skill to proficiency level, years
  of experience, concrete evidence, and applicable roles. Single source of truth for
  what the candidate can credibly claim.

- **Resume Structures** — Role-specific YAML files that define section order, emphasis
  areas, keyword targets, and which skill categories to prioritize. Currently supports:
  Data Engineer, Analytics Engineer, Solutions Engineer, Platform Architect.

- **Master Portfolio** — Complete, unfiltered career record covering all roles from
  Kinsmen Homes (2011) through QuotaPath (2024–present). Includes responsibilities,
  impact metrics, confirmed contributions, and environment details per role.

- **Fit Evaluation** — Structured 8-section analysis comparing candidate skills against
  a specific JD. Produces a 1-10 fit score, skill match matrix, gap analysis,
  positioning strategy, and an APPLY / APPLY WITH CAVEATS / SKIP recommendation.

- **Cover Letter** — Tailored letter generated from the fit evaluation's positioning
  strategy, gap mitigation notes, and the candidate's strongest matching evidence.

- **Archive** — Raw material (old resumes, interview prep notes, job descriptions) that
  feeds into the taxonomy over time. Includes both PDFs and a detailed CSV of
  interview answers, accomplishments, and an "elevator pitch."

- **Career Strategy** — Central decision-making document covering career identity,
  dual-track strategy (FTE + contract/gig), target role matrix, LinkedIn optimization,
  decision framework, skill development priorities, and search cadence. Lives at
  `job-search/career-strategy.yaml`.

- **Job Search Strategy** — Maintained search queries for job boards, recommended titles
  based on the candidate's experience, and a list of tracked sites (FTE and contract).

- **Audit Trail** — Periodic legitimacy sweeps that cross-reference taxonomy claims
  against confirmed evidence, flag LLM-generated inflation from old resumes, and
  ensure proficiency levels are honest.

## Generation Modes

| Mode | Flag | Output | Purpose |
|---|---|---|---|
| Resume | `--mode resume` | `prompt-resume-*.md` | ATS-optimized one-page resume |
| Fit Evaluation | `--mode fit-eval` | `prompt-fit-eval-*.md` | Should-I-apply analysis |
| Cover Letter | `--mode cover-letter` | `prompt-cover-letter-*.md` | Tailored cover letter |

## Requirements

```bash
pip install pyyaml
```
