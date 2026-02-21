# Resume Standards & Formatting Guide

Global rules that apply to all generated resumes regardless of target role.

## General Principles

1. **One page** unless the role explicitly calls for more (staff+ level, academic)
2. **Tailored to the job** — every bullet should map to a requirement in the posting
3. **Impact over responsibility** — lead with metrics, outcomes, scale; not just what you did
4. **Recency bias** — most recent and relevant roles get the most space
5. **No fluff** — remove soft-skill bullets unless they demonstrate measurable leadership
6. **ATS-friendly** — no tables, columns, graphics, or headers inside text boxes

## Bullet Formula

Every experience bullet should follow this pattern where possible:

```
[Action verb] + [what you built/did] + [technical context] + [measurable result]
```

Examples:
- "Architected Medallion-style warehousing layers in dbt Cloud, scaling to 1,900+ models across 6 enterprise domains"
- "Reduced data incident rate by 40% by implementing automated freshness and schema validation tests across 90+ pipelines"
- "Designed CI/CD pipelines via GitHub Actions, increasing deployment frequency 2x while reducing hotfixes by 30%"

When metrics are unavailable, use **scale indicators**: row counts, model counts, team size, number of stakeholders, pipeline counts.

## Section Order (Default)

1. Header (name, contact, links)
2. Summary (2-3 sentences, tailored per application)
3. Technical Skills (grouped by category, ordered by relevance to role)
4. Experience (reverse chronological)
5. Projects (if relevant to role)
6. Education
7. Leadership / Community (optional, space permitting)

## Section-Specific Rules

### Summary
- 2-3 sentences maximum
- First sentence: identity + years of experience + core domain
- Second sentence: key specializations relevant to the target role
- Third sentence (optional): differentiator or cross-functional strength
- MUST be rewritten for every application

### Technical Skills
- Group into categories: Languages, Data Engineering, Cloud, Databases, Analytics, Practices
- Order categories by relevance to the target role
- Within each category, order skills by proficiency (strongest first)
- Include version numbers or specifics where impressive (e.g., "dbt Cloud (3+ years, 1,900+ models)")
- Omit skills below "working knowledge" unless they appear in the job description

### Experience
- 3-5 bullets per role (most recent role can have up to 6)
- Lead each bullet with a strong action verb (see verb bank below)
- Include environment/tech stack as a sub-header or inline
- Prioritize bullets that match the target job description
- Older roles (3+ years ago) can be condensed to 2-3 bullets

### Projects
- Only include if they demonstrate skills not covered by work experience
- Or if they show initiative relevant to the target role
- 2-3 bullets maximum per project

### Education
- Degree, institution, year
- Omit GPA unless exceptional and recent (<3 years)

## Action Verb Bank

### Building / Creating
Architected, Built, Created, Designed, Developed, Engineered, Implemented, Launched

### Improving / Optimizing
Accelerated, Automated, Enhanced, Improved, Optimized, Reduced, Refactored, Streamlined

### Leading / Collaborating
Championed, Coordinated, Led, Managed, Mentored, Partnered, Spearheaded

### Analyzing / Investigating
Analyzed, Audited, Conducted, Diagnosed, Evaluated, Identified, Investigated, Validated

### Delivering / Supporting
Delivered, Documented, Enabled, Established, Maintained, Scaled, Supported

## Role-Specific Overrides

Each role type has a structure file in `templates/structures/` that can override:
- Section order
- Skill category prioritization
- Which experience bullets to emphasize
- Summary tone and focus
- Whether to include projects section

## Output Format (Rezi-Compatible Plain Text)

Generated resumes must be **plain text** that can be pasted directly into Rezi
or similar resume builder tools. This means:

- NO markdown formatting: no `**bold**`, no `# headers`, no `---` dividers
- NO bullet point characters like `*` or `-` at the start of lines
- Use simple line breaks and ALL CAPS for section headers
- Use indentation (2-4 spaces) to visually group content under a role
- Skill categories use a "Category: item, item, item" format on a single line
- Experience bullets start directly with the action verb, one per line
- Each role block: Title -- Company \n Dates | Location \n then bullets below

Example format:

```
JAMES PATRICK MAYO
New York, NY | email@example.com | linkedin.com/in/profile

SUMMARY
Integration-focused engineer with 7+ years of experience...

TECHNICAL SKILLS
Integrations & APIs: REST APIs, Salesforce API, Webhooks, CRM Integrations
Languages: Python (4yr), SQL (7yr)
Automation: GitHub Actions, CircleCI, Jenkins, Automated Testing

EXPERIENCE

Solutions Engineer / Data Platform Architect -- QuotaPath
Aug 2024 - Sep 2025 | Remote

Designed and maintained integrations across 10+ enterprise SaaS platforms
Built automated data validation frameworks reducing incidents by 50%+
Developed Python-based automation workflows reducing runtimes from hours to minutes

EDUCATION
B.B.A. in Management Information Systems -- Lamar University, 2018
```

## Visual Formatting (for final PDF export from Rezi)

- Font: Clean sans-serif (Calibri, Arial, Helvetica)
- Font size: 10-11pt body, 12-14pt name
- Margins: 0.5-0.75 inches
- Line spacing: 1.0-1.15
