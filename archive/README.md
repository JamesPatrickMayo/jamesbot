# archive/

This directory stores raw job descriptions and reference materials used as inputs to the resume generation workflow.

## What belongs here

- **`job-desc-[company]-[role].txt`** — Raw job description text, fetched and saved before running a fit evaluation. Used as the primary input to the fit evaluation and resume generation prompts.
- **Career reference documents** (PDFs, etc.) — Personal career planning documents, old resumes, or prior cover letters used to populate `portfolio/master-portfolio.yaml`. These are `.gitignore`d and should never be committed.

## Naming convention

```
job-desc-[company-slug]-[role-slug].txt
```

Examples:
- `job-desc-hibob-implementation-manager.txt`
- `job-desc-lightdash-analytics-engineering-advocate.txt`
- `job-desc-empassion-data-engineer.txt`

## Workflow

1. Find a job posting on LinkedIn or a company careers page
2. Fetch the full job description text (use the Cursor agent or copy manually)
3. Save it here following the naming convention
4. Run the fit evaluation prompt referencing this file
5. If fit score >= 7.5, run resume and cover letter generation
6. Outputs land in `output/`
