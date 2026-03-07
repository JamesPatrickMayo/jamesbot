# Output (generated artifacts)

Generated files from the pipeline are **local only** and not committed to this repo:

- `application-*.md` — per-job fit evaluations, gap analyses, and prompts
- `study-guide-*.md` — role-specific interview prep
- `resume-*.md` — tailored resume output per application
- `tracker.yaml` — your application history and status log

See `.gitignore` for the exact patterns. Run `python scripts/evaluate.py` and `scripts/tracker.py` to generate these locally.
