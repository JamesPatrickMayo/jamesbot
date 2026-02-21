# JamesBot — AI Resume & Application Generation System

> **This is a working proof-of-concept** — a real system built and used for active job searching,
> open-sourced as a template for others to fork and adapt.
> The portfolio data in this repo is placeholder-only. See the [Setup](#setup) section to populate it with your own.

**Author:** [James Patrick Mayo](https://linkedin.com/in/jamespatrickmayo) · [GitHub](https://github.com/JamesPatrickMayo)

A structured, maintainable system that maintains a canonical skills database and
produces tailored resumes, fit evaluations, and cover letters for specific job
applications. The system uses a preprocessing pipeline to reduce LLM cognitive
load — parsing JDs, pre-scoring skill matches, and pre-selecting content — so the
LLM validates and refines rather than deriving everything from scratch.

## Architecture

```
jamesbot/
├── portfolio/                        # Canonical skills database
│   ├── master-portfolio.yaml         # Full career history, responsibilities, impact metrics
│   ├── skill-taxonomy.yaml           # Normalized: role → skill → proficiency → evidence
│   ├── questionnaire.yaml            # Expansion questions + responses
│   ├── skill-development.yaml        # Skill gaps, learning roadmap, interview prep, resources
│   ├── bullet-bank.yaml              # Pre-written, tagged bullet variants per role+company
│   └── paragraph-bank.yaml          # Pre-written cover letter paragraph blocks by scenario
│
├── templates/                        # Format definitions & reusable schemas
│   ├── resume-standards.md           # Global resume formatting rules and conventions
│   ├── fit-evaluation-structure.yaml # Reusable fit evaluation schema (8 sections)
│   ├── cover-letter-structure.yaml   # Cover letter generation schema
│   ├── linkedin-optimization.yaml    # LinkedIn profile section-by-section recommendations
│   └── structures/                   # Role-specific resume structures
│       ├── data-engineer.yaml
│       ├── analytics-engineer.yaml
│       ├── solutions-engineer.yaml
│       └── platform-architect.yaml
│
├── scripts/
│   ├── evaluate.py                   # Unified orchestrator (one command → full workflow)
│   ├── jd_parser.py                  # Parse raw JD text → structured YAML
│   ├── scorer.py                     # Pre-score skills against JD keywords
│   ├── generate_resume.py            # Assemble enriched LLM prompts
│   ├── tracker.py                    # Application tracker (add/update/status/export-csv)
│   └── fetch_jd.py                   # Fetch job URLs and save to archive/
│
├── archive/                          # Unstructured source material
│   ├── job-desc-*.txt                # Saved job descriptions (one per application)
│   ├── jd-parsed-*.yaml              # Parsed JD output (from jd_parser.py)
│   ├── jd-scores-*.yaml              # Pre-scored skill matches (from scorer.py)
│   └── *.pdf / *.csv                 # Old resumes, interview prep notes
│
├── job-search/                       # Job search strategy & tracking
│   ├── career-strategy.yaml          # Central career strategy (identity, dual-track, decisions)
│   └── search-strategy.yaml          # Search queries, recommended titles, sites
│
├── output/                           # Generated artifacts
│   ├── tracker.yaml                  # Application history and status log
│   ├── application-*.md              # Consolidated per-job files (fit eval + prompts)
│   └── tracker.csv                   # Exported spreadsheet (from tracker.py --export-csv)
│
└── .cursor/rules/
    └── resume-system.mdc             # Cursor rules for maintaining this system
```

## Quickstart

### New application (full pipeline)

```bash
# Option A — start with a URL (auto-fetches and saves the JD)
python scripts/fetch_jd.py --url "https://jobs.lever.co/company/abc123" --company "Merge" --role "Solutions Engineer"

# Option B — manually save the JD first
# paste job description text → archive/job-desc-merge-solutions-engineer.txt

# Run the full pipeline: parse → score → detect role → generate → track → gap-sync
python scripts/evaluate.py --job archive/job-desc-merge-solutions-engineer.txt
```

The orchestrator walks you through each step interactively.

### Check application status

```bash
python scripts/tracker.py --status
python scripts/tracker.py --update --company "Merge" --app-status interviewing --notes "Phone screen Feb 28"
python scripts/tracker.py --export-csv
```

### Manual pipeline (step by step)

```bash
# 1. Parse JD
python scripts/jd_parser.py --job archive/job-desc-merge-se.txt

# 2. Score skills
python scripts/scorer.py --jd archive/job-desc-merge-se.txt \
    --parsed-jd archive/jd-parsed-merge-se-2026-02-20.yaml --summary

# 3. Generate enriched prompts (LLM validates pre-computed context)
python scripts/generate_resume.py \
    --job archive/job-desc-merge-se.txt \
    --role solutions-engineer \
    --mode fit-eval \
    --parsed-jd archive/jd-parsed-merge-se-2026-02-20.yaml \
    --pre-scores archive/jd-scores-merge-se-2026-02-20.yaml

# 4. Generate resume with pre-selected bullets from bullet bank
python scripts/generate_resume.py \
    --job archive/job-desc-merge-se.txt \
    --role solutions-engineer \
    --mode resume \
    --parsed-jd archive/jd-parsed-merge-se-2026-02-20.yaml \
    --pre-scores archive/jd-scores-merge-se-2026-02-20.yaml \
    --bullet-bank   # uses portfolio/bullet-bank.yaml automatically

# 5. Cover letter with pre-selected paragraph blocks
python scripts/generate_resume.py \
    --job archive/job-desc-merge-se.txt \
    --role solutions-engineer \
    --mode cover-letter \
    --fit-eval output/application-merge-se-2026-02-20.md \
    --paragraph-bank

# 6. Add to tracker manually
python scripts/tracker.py --add \
    --company "Merge" --role "Solutions Engineer" --fit 8.5 \
    --recommendation "APPLY" --app-status applied
```

## Data Flow

```
Job URL  ──►  fetch_jd.py  ──►  archive/job-desc-*.txt
                                         │
                                         ▼
                              jd_parser.py  ──►  archive/jd-parsed-*.yaml
                                         │
                                         ▼
                               scorer.py  ──►  archive/jd-scores-*.yaml
                                         │
                            ┌────────────┘
                            │    + bullet-bank.yaml
                            │    + paragraph-bank.yaml
                            ▼
                     generate_resume.py  ──►  output/prompt-*.md
                            │
                            ▼
                     Cursor Agent  ──►  output/application-*.md
                            │
                  ┌─────────┴───────────┐
                  ▼                     ▼
           tracker.yaml           skill-development.yaml
        (application log)          (auto-appended gaps)
```

**LLM role shift:** Without pre-computed context, the LLM discovers structure,
scores skills, and generates from scratch. With `--parsed-jd` + `--pre-scores`,
it validates scores, adjusts where warranted, and refines — substantially reducing
reasoning load and improving consistency.

## Key Concepts

- **Skill Taxonomy** — Normalized table mapping each skill to proficiency level, years
  of experience, concrete evidence, and applicable roles. Single source of truth for
  what the candidate can credibly claim.

- **Resume Structures** — Role-specific YAML files defining section order, emphasis
  areas, keyword targets, and which skill categories to prioritize. Supports:
  Data Engineer, Analytics Engineer, Solutions Engineer, Platform Architect.

- **JD Parser** — Extracts structure and keywords from raw JD text without external
  NLP dependencies. Detects seniority signals, required vs. preferred skills, and
  high-signal context keywords.

- **Pre-Scorer** — Matches each taxonomy skill against JD mentions using a weighted
  keyword index. Strong matches (7+/10) are surfaced for the LLM to validate rather
  than rediscover. Includes gap detection for intermediate+ skills absent from the JD.

- **Bullet Bank** — Pre-written resume bullet variants per company, tagged by skill
  cluster and applicable role. The assembler pre-selects the top N bullets by JD
  keyword overlap; the LLM reorders and tightens, not rewrites from scratch.

- **Paragraph Bank** — Pre-written cover letter paragraphs for recurring scenarios
  (build-from-scratch, client-facing scale, domain gap bridge, career narrative).
  Tagged by applicable role; top 2-3 selected before the LLM pass.

- **Application Tracker** — `output/tracker.yaml` logs every evaluated role with
  fit score, recommendation, status, and output file path. `tracker.py` provides
  CLI commands to add, update, print status, and export to CSV.

- **Gap Sync** — `evaluate.py` scans application outputs for MODERATE/CRITICAL GAP
  mentions and auto-appends them to `portfolio/skill-development.yaml` gap log,
  keeping the learning roadmap in sync with the application pipeline.

- **Master Portfolio** — Complete, unfiltered career record. The single source of
  truth for experience, impact metrics, and confirmed contributions.

- **Career Strategy** — Central decision-making document at `job-search/career-strategy.yaml`
  covering career identity, dual-track strategy, target role matrix, decision framework,
  and skill development priorities.

## Generation Modes

| Mode | Flag | LLM Task |
|---|---|---|
| Fit Evaluation | `--mode fit-eval` | Validate pre-scores, fill matrix, produce APPLY/SKIP |
| Resume | `--mode resume` | Validate bullets, reorder by relevance, mirror JD keywords |
| Cover Letter | `--mode cover-letter` | Stitch pre-selected paragraphs, adapt tone to company |

## Tracker Status Values

| Status | Meaning |
|---|---|
| `applied` | Application submitted |
| `interviewing` | Active in interview process |
| `offer` | Offer received |
| `rejected` | Rejection received |
| `ghosted` | No response after 3+ weeks |
| `skipped` | Evaluated but did not apply (low score, domain gap, etc.) |
| `pending_application` | Fit score ≥ 7.5 but not yet applied |
| `pending_evaluation` | JD was incomplete; re-evaluate with full JD |

## Maintenance

- When you gain new skills or complete projects, update `skill-taxonomy.yaml`
- When experience accumulates, add bullets to `bullet-bank.yaml` with tags
- Periodically review `questionnaire.yaml` for unanswered expansion prompts
- Review `job-search/career-strategy.yaml` to update search focus as needs change
- Run `tracker.py --status` weekly to maintain application momentum
- See `.cursor/rules/resume-system.mdc` for Cursor agent conventions

## Requirements

```bash
pip install pyyaml

# Optional — enables fetch_jd.py URL fetching
pip install requests beautifulsoup4
```

## Setup

To use this system with your own data:

1. **Fork or clone** this repository
2. **Replace portfolio files** with your own data:
   - `portfolio/master-portfolio.yaml` — your career history, responsibilities, impact metrics
   - `portfolio/skill-taxonomy.yaml` — your skills, proficiency levels, evidence
   - `portfolio/bullet-bank.yaml` — your pre-written bullet variants (follow the schema)
   - `portfolio/paragraph-bank.yaml` — your cover letter paragraph blocks
3. **Update templates/structures/** — adjust keyword targets for the roles you target
4. **Run your first evaluation:**
   ```bash
   # Save a job description
   python scripts/fetch_jd.py --url "https://jobs.lever.co/..." --company "Acme" --role "Data Engineer"
   # Run the full pipeline
   python scripts/evaluate.py --job archive/job-desc-acme-data-engineer.txt
   ```

The `questionnaire.yaml` file contains expansion prompts to help you think through skills
and experiences that are easy to forget — fill it in over time to strengthen your portfolio.

## License

MIT — fork, adapt, and use freely.
