# jamesbot — AI-Powered Resume & Application System

A personal AI system that functions as a **canonical skills database** and automates the creation of tailored job application materials: fit evaluations, resumes, and cover letters — all from a single source of truth.

Built to run inside [Cursor](https://cursor.sh) as an AI agent workflow. No code to run; just open the project, paste a job description, and the agent generates a complete application package.

---

## What this does

1. **Evaluates job fit** — Scores a job posting against your skills and experience profile (0–10), with a structured gap analysis and recommendation (Apply / Skip / Investigate)
2. **Generates a tailored resume** — Pulls from your canonical portfolio YAML, selects and reorders bullets based on the job's priorities, adjusts language to match the JD
3. **Writes a cover letter** — Structured, voice-consistent, human-sounding, with built-in countermeasures for AI detection
4. **Maintains a career strategy** — Dual-track job search (FTE + contract), target role matrix organized by transferable skill clusters, LinkedIn optimization, and decision framework

All outputs are saved as `.md` files in `output/`. All configuration is in YAML.

---

## Project structure

```
jamesbot/
├── portfolio/
│   ├── master-portfolio.yaml        # Canonical source of truth: all experience, projects, metrics
│   ├── skill-taxonomy.yaml          # Skills with proficiency levels, evidence, and applicable roles
│   └── questionnaire.yaml           # Q&A to expand and strengthen the portfolio over time
│
├── templates/
│   ├── fit-evaluation-structure.yaml    # Schema for consistent fit evaluations
│   ├── cover-letter-structure.yaml      # Cover letter schema + writing style + AI detection countermeasures
│   ├── resume-standards.md              # Resume formatting rules and constraints
│   ├── linkedin-optimization.yaml       # Section-by-section LinkedIn profile recommendations
│   └── structures/                      # Role-specific resume structures
│       ├── solutions-engineer.yaml
│       ├── data-engineer.yaml
│       ├── analytics-engineer.yaml
│       └── platform-architect.yaml
│
├── prompts/
│   ├── fit-evaluation.md            # Agent prompt: evaluate a job posting
│   ├── resume-generator.md          # Agent prompt: generate a tailored resume
│   └── cover-letter.md              # Agent prompt: generate a cover letter
│
├── job-search/
│   ├── career-strategy.yaml         # Dual-track strategy, target role matrix, decision framework
│   └── search-strategy.yaml         # Search queries, platforms, and cadence
│
├── archive/
│   ├── README.md                    # How to use this directory
│   └── job-desc-*.txt               # Raw job descriptions (inputs to the workflow)
│
├── output/
│   └── application-[company]-[role]-[date].md   # Generated fit evals, resumes, cover letters
│
├── scripts/
│   └── generate_resume.py           # Utility script for resume generation
│
└── .cursor/
    └── rules/
        └── resume-system.mdc        # Cursor agent rules that govern the entire workflow
```

---

## How to use it

### Prerequisites

- [Cursor](https://cursor.sh) — the AI agent runs natively here
- Basic familiarity with YAML

### Setup

1. **Fork or clone this repo**

2. **Populate your portfolio files**
   - `portfolio/master-portfolio.yaml` — your full career history, projects, education
   - `portfolio/skill-taxonomy.yaml` — your skills with evidence and proficiency levels
   - Work through `portfolio/questionnaire.yaml` to surface details you might have left out

3. **Update career strategy**
   - `job-search/career-strategy.yaml` — adjust the dual-track strategy, target roles, and decision framework to match your goals

4. **Open the project in Cursor**
   - The `.cursor/rules/resume-system.mdc` file automatically loads the system context for the AI agent

### Workflow: evaluating a job

1. Find a job posting
2. Save the raw job description text to `archive/job-desc-[company]-[role].txt`
3. In Cursor chat, say:

   > Evaluate this role: [paste job URL or reference the archive file]

4. The agent will:
   - Score the fit (0–10) using `templates/fit-evaluation-structure.yaml`
   - Identify your strengths, gaps, and positioning strategy
   - Recommend Apply / Skip / Investigate
   - If score ≥ 7.5: generate a tailored resume and cover letter automatically
   - Save everything to `output/application-[company]-[role]-[date].md`

---

## Key concepts

### The canonical portfolio

`master-portfolio.yaml` is the **single source of truth** for all career information. Every resume generated pulls from this file. You never write a resume from scratch — you curate the source and let the agent select and tailor.

### Skill taxonomy

`skill-taxonomy.yaml` maps each skill to:
- Proficiency level (foundational / intermediate / advanced / expert)
- Years of experience
- Concrete evidence (specific accomplishments, not generic claims)
- Roles where the skill is applicable

The fit evaluation uses this to score JD requirements against demonstrated evidence, not just keyword presence.

### Dual-track strategy

`career-strategy.yaml` separates the job search into two parallel tracks:
- **Track A (FTE)** — full-time employment, target org profile, domain preferences
- **Track B (Contract/Gig)** — parallel income track, acceptable rates and durations, platforms

### AI detection countermeasures

`templates/cover-letter-structure.yaml` includes a documented section on how AI detectors work (perplexity, burstiness, pattern recognition) and specific writing rules the agent applies to generate cover letters that read as human-written.

---

## Example outputs

The `output/` directory contains real application packages generated by this system. Each file includes:

- Full fit evaluation with a scored skill match matrix
- Gap analysis and positioning strategy
- Tailored resume
- Cover letter

---

## Customization

To adapt this for yourself:

| File | What to change |
|---|---|
| `portfolio/master-portfolio.yaml` | Replace all experience, education, and projects with your own |
| `portfolio/skill-taxonomy.yaml` | Replace skills and evidence with your own |
| `job-search/career-strategy.yaml` | Replace target roles, domains, and preferences |
| `templates/structures/` | Add or modify role-specific resume structures for your target roles |
| `templates/cover-letter-structure.yaml` | Adjust writing style preferences in the `voice_and_style` section |

---

## Built by

James Mayo — [linkedin.com/in/jamespatrickmayo](https://linkedin.com/in/jamespatrickmayo)

The portfolio data in this repo (skills, experience, projects) is James's real career history, provided as a working example. Fork it and replace with your own.

---

## License

MIT — use this freely, adapt it, build on it.
