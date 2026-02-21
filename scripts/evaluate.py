#!/usr/bin/env python3
"""
Evaluate — unified orchestrator for the jamesbot application pipeline.

Runs the full workflow in a single command:
    1. Parse the raw JD (jd_parser.py)
    2. Pre-score skills against taxonomy (scorer.py)
    3. Auto-detect best role template (or accept --role override)
    4. Print pre-score summary and ask what to generate
    5. Run generate_resume.py with pre-computed context injected
    6. Auto-append the application to output/tracker.yaml
    7. Scan output for skill gaps and append to skill-development.yaml log

Usage:
    python scripts/evaluate.py --job archive/job-desc-hibob-implementation-manager.txt
    python scripts/evaluate.py --job archive/job-desc-hibob.txt --role solutions-engineer
    python scripts/evaluate.py --job archive/job-desc-hibob.txt --mode fit-only
    python scripts/evaluate.py --job archive/job-desc-hibob.txt --mode all --no-interact

Modes:
    all         Run fit-eval → resume → cover-letter (default)
    fit-only    Run fit evaluation only
    resume      Run fit-eval + resume (no cover letter)
    skip        Parse + score + print summary only (no generation)
"""

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
STRUCTURES_DIR = ROOT / "templates" / "structures"
SKILL_DEV_PATH = ROOT / "portfolio" / "skill-development.yaml"
OUTPUT_DIR = ROOT / "output"
ARCHIVE_DIR = ROOT / "archive"

PYTHON = sys.executable


# ---- YAML helpers -----------------------------------------------------------

def load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_yaml(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


# ---- Role auto-detection ----------------------------------------------------

def auto_detect_role(jd_text: str) -> tuple[str, float]:
    """
    Score each role template against the JD text and return the best match.
    Returns: (role_slug, confidence_0_to_10)
    """
    jd_lower = jd_text.lower()
    best_role = "solutions-engineer"
    best_score = 0.0

    for struct_path in STRUCTURES_DIR.glob("*.yaml"):
        try:
            structure = load_yaml(struct_path)
        except Exception:
            continue

        score = 0.0
        # Role variants: strong signal (2 pts each)
        for variant in structure.get("role_variants", []):
            if variant.lower() in jd_lower:
                score += 2.0

        # Must-include keywords (1 pt each)
        kt = structure.get("keyword_targets", {})
        for kw in kt.get("must_include", []):
            if kw.lower() in jd_lower:
                score += 1.0

        # Should-include keywords (0.5 pt each)
        for kw in kt.get("should_include", []):
            if kw.lower() in jd_lower:
                score += 0.5

        if score > best_score:
            best_score = score
            best_role = struct_path.stem

    # Normalize to 0–10
    confidence = round(min(10.0, best_score), 1)
    return best_role, confidence


def list_available_roles() -> list[str]:
    return [p.stem for p in STRUCTURES_DIR.glob("*.yaml")]


# ---- Subprocess runners -----------------------------------------------------

def run_parser(jd_path: Path, company: str | None = None, role_hint: str | None = None) -> Path:
    """Run jd_parser.py and return the output path."""
    slug = jd_path.stem.replace("job-desc-", "")
    out = ARCHIVE_DIR / f"jd-parsed-{slug}-{date.today()}.yaml"

    if out.exists():
        print(f"  [cache] Parsed JD already exists: {out.name}  (delete to re-parse)")
        return out

    cmd = [PYTHON, str(ROOT / "scripts" / "jd_parser.py"), "--job", str(jd_path)]
    if company:
        cmd += ["--company", company]
    if role_hint:
        cmd += ["--role", role_hint]
    cmd += ["--output", str(out)]

    print("  [1/7] Parsing job description...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [!] Parser error:\n{result.stderr}")
        sys.exit(1)
    print(f"       {result.stdout.strip().splitlines()[-1] if result.stdout else out}")
    return out


def run_scorer(jd_path: Path, parsed_jd_path: Path) -> Path:
    """Run scorer.py and return the output path."""
    slug = jd_path.stem.replace("job-desc-", "")
    out = ARCHIVE_DIR / f"jd-scores-{slug}-{date.today()}.yaml"

    if out.exists():
        print(f"  [cache] Scores already exist: {out.name}  (delete to re-score)")
        return out

    cmd = [
        PYTHON, str(ROOT / "scripts" / "scorer.py"),
        "--jd", str(jd_path),
        "--parsed-jd", str(parsed_jd_path),
        "--output", str(out),
    ]

    print("  [2/7] Scoring skills against taxonomy...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [!] Scorer error:\n{result.stderr}")
        sys.exit(1)
    print(f"       {result.stdout.strip().splitlines()[-1] if result.stdout else out}")
    return out


def run_generate(
    jd_path: Path,
    role: str,
    mode: str,
    parsed_jd_path: Path,
    scores_path: Path,
    output_path: str,
    fit_eval_path: str | None = None,
    use_bullet_bank: bool = True,
    use_paragraph_bank: bool = True,
) -> Path:
    """Run generate_resume.py and return the output path."""
    cmd = [
        PYTHON, str(ROOT / "scripts" / "generate_resume.py"),
        "--job", str(jd_path),
        "--role", role,
        "--mode", mode,
        "--parsed-jd", str(parsed_jd_path),
        "--pre-scores", str(scores_path),
        "--output", output_path,
    ]
    if fit_eval_path:
        cmd += ["--fit-eval", fit_eval_path]

    # Add content banks if they exist
    bullet_bank = ROOT / "portfolio" / "bullet-bank.yaml"
    paragraph_bank = ROOT / "portfolio" / "paragraph-bank.yaml"
    if use_bullet_bank and bullet_bank.exists() and mode in ("resume",):
        cmd += ["--bullet-bank", str(bullet_bank)]
    if use_paragraph_bank and paragraph_bank.exists() and mode in ("cover-letter",):
        cmd += ["--paragraph-bank", str(paragraph_bank)]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [!] generate_resume error:\n{result.stderr}")
        sys.exit(1)
    last_line = result.stdout.strip().splitlines()[-1] if result.stdout else output_path
    print(f"       {last_line}")
    return Path(output_path)


# ---- Tracker integration ----------------------------------------------------

def add_to_tracker(
    company: str,
    role_title: str,
    fit_score: float | None,
    recommendation: str,
    output_file: str,
    status: str = "applied",
) -> None:
    """Append a new entry to output/tracker.yaml."""
    cmd = [
        PYTHON, str(ROOT / "scripts" / "tracker.py"),
        "--add",
        "--company", company,
        "--role", role_title,
        "--recommendation", recommendation,
        "--app-status", status,
        "--output-file", output_file,
    ]
    if fit_score is not None:
        cmd += ["--fit", str(fit_score)]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  [6/7] Tracker: {result.stdout.strip()}")
    else:
        print(f"  [!] Tracker warning: {result.stderr.strip()}")


# ---- Gap sync ---------------------------------------------------------------

def _extract_gap_mentions(text: str) -> list[str]:
    """
    Scan application output for gap mentions.
    Looks for MODERATE GAP, CRITICAL GAP, STRONG GAP, and skill gap patterns.
    """
    gaps = []
    # Table rows mentioning gaps: | Skill Name | ... | MODERATE GAP | ... |
    for pattern in [
        r"\|\s*(.+?)\s*\|\s*(?:MODERATE|CRITICAL|STRONG|SIGNIFICANT)\s+GAP",
        r"(?:MODERATE|CRITICAL|STRONG)\s+GAP[^\n]*?:\s*([A-Z][a-z].{3,60}?)(?:\n|$)",
        r"\*\*Gap[s]?:\*\*\s*(.+?)(?:\n|$)",
    ]:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            gap = m.group(1).strip().strip("|").strip()
            if gap and len(gap) > 3:
                gaps.append(gap)
    return list(dict.fromkeys(gaps))  # deduplicate while preserving order


def sync_gaps_to_skill_development(output_file: Path, company: str, role_title: str) -> int:
    """
    Scan the output .md file for gap mentions and append them to
    portfolio/skill-development.yaml under the gap_tracking_log section.
    Returns number of gaps appended.
    """
    if not output_file.exists():
        return 0

    text = output_file.read_text(encoding="utf-8")
    gaps = _extract_gap_mentions(text)
    if not gaps:
        return 0

    if not SKILL_DEV_PATH.exists():
        print(f"  [!] skill-development.yaml not found; skipping gap sync.")
        return 0

    skill_dev = load_yaml(SKILL_DEV_PATH)

    # Navigate or create the gap_tracking_log section
    if "gap_tracking_log" not in skill_dev:
        skill_dev["gap_tracking_log"] = []

    log = skill_dev["gap_tracking_log"]
    new_entry = {
        "evaluation_date": str(date.today()),
        "company": company,
        "role": role_title,
        "source_file": str(output_file.relative_to(ROOT)).replace("\\", "/"),
        "gaps_identified": gaps,
    }
    log.append(new_entry)

    save_yaml(SKILL_DEV_PATH, skill_dev)
    return len(gaps)


# ---- Summary printer --------------------------------------------------------

def print_prescore_summary(parsed_jd: dict, scores: dict) -> None:
    summary = scores.get("summary", {})
    company = parsed_jd.get("company", "?")
    role_title = parsed_jd.get("inferred_role", "?")
    seniority = parsed_jd.get("seniority", "unknown")

    print()
    print("=" * 60)
    print(f"  PRE-SCORE SUMMARY: {company} — {role_title}")
    print("=" * 60)
    print(f"  Seniority signal    : {seniority}")
    print(f"  Estimated fit       : {summary.get('estimated_fit_score', '?')}/10")
    print(f"  Strong matches      : {summary.get('strong_match_count', 0)}")
    print(f"  Partial matches     : {summary.get('partial_match_count', 0)}")
    top = summary.get("top_matching_skills", [])
    if top:
        print(f"  Top skills          : {', '.join(top[:6])}")
    gaps = summary.get("likely_gaps", [])
    if gaps:
        print(f"  Likely gaps         : {', '.join(gaps[:4])}")
    print("=" * 60)
    print()


# ---- Main -------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="End-to-end orchestrator: parse → score → generate → track → gap-sync"
    )
    parser.add_argument("--job", required=True, help="Path to raw JD text file")
    parser.add_argument(
        "--role",
        choices=list_available_roles(),
        help="Role template (auto-detected if not specified)",
    )
    parser.add_argument(
        "--company", help="Company name override (default: inferred from filename)"
    )
    parser.add_argument(
        "--mode",
        choices=["all", "fit-only", "resume", "skip"],
        default="all",
        help="Generation mode: all (default), fit-only, resume, skip (summary only)",
    )
    parser.add_argument(
        "--no-interact",
        action="store_true",
        dest="no_interact",
        help="Skip interactive prompts; proceed with defaults",
    )
    parser.add_argument(
        "--output",
        help="Base output file path (default: output/application-{slug}-{date}.md)",
    )
    args = parser.parse_args()

    jd_path = Path(args.job)
    if not jd_path.exists():
        print(f"Error: JD file not found: {jd_path}")
        sys.exit(1)

    print(f"\njamesbot evaluate: {jd_path.name}")
    print("-" * 60)

    # ---- Step 1: Parse JD ---------------------------------------------------
    parsed_jd_path = run_parser(jd_path, args.company)
    parsed_jd = load_yaml(parsed_jd_path)
    company = parsed_jd.get("company", "Unknown")
    role_title = parsed_jd.get("inferred_role", "Unknown")

    # ---- Step 2: Score skills -----------------------------------------------
    scores_path = run_scorer(jd_path, parsed_jd_path)
    scores = load_yaml(scores_path)

    # ---- Step 3: Auto-detect role -------------------------------------------
    jd_text = jd_path.read_text(encoding="utf-8")
    detected_role, detect_confidence = auto_detect_role(jd_text)

    if args.role:
        chosen_role = args.role
        print(f"  [3/7] Role: {chosen_role}  (user-specified; auto-detected: {detected_role})")
    else:
        chosen_role = detected_role
        print(f"  [3/7] Role auto-detected: {chosen_role}  (confidence: {detect_confidence}/10)")

    # ---- Step 4: Print pre-score summary ------------------------------------
    print_prescore_summary(parsed_jd, scores)
    fit_estimate = scores.get("summary", {}).get("estimated_fit_score", 0)

    # ---- Step 5: Confirm generation mode ------------------------------------
    mode = args.mode
    if not args.no_interact and mode == "all":
        print(f"  Pre-score: {fit_estimate}/10  |  Suggested role: {chosen_role}")
        print()
        print("  Generate: [a]ll  [f]it-only  [r]esume  [s]kip  [role: type name]")
        answer = input("  Your choice [a]: ").strip().lower() or "a"

        if answer in ("a", "all", ""):
            mode = "all"
        elif answer in ("f", "fit", "fit-only"):
            mode = "fit-only"
        elif answer in ("r", "resume"):
            mode = "resume"
        elif answer in ("s", "skip"):
            mode = "skip"
        elif answer in list_available_roles():
            chosen_role = answer
            mode = "all"
            print(f"  Role overridden to: {chosen_role}")

    if mode == "skip":
        print("\n  [skip] Stopping after pre-score summary. No output generated.")
        return

    # ---- Output file naming -------------------------------------------------
    slug = jd_path.stem.replace("job-desc-", "")
    if args.output:
        base_output = args.output
    else:
        base_output = str(OUTPUT_DIR / f"application-{slug}-{date.today()}.md")

    # ---- Step 5a: Fit evaluation --------------------------------------------
    fit_eval_path = None
    if mode in ("all", "fit-only", "resume"):
        print(f"\n  [4/7] Generating fit evaluation  →  {Path(base_output).name}")
        # Write fit-eval to a temp file, then we'll merge into the main output
        fit_eval_out = str(OUTPUT_DIR / f"_tmp-fit-eval-{slug}.md")
        run_generate(
            jd_path=jd_path,
            role=chosen_role,
            mode="fit-eval",
            parsed_jd_path=parsed_jd_path,
            scores_path=scores_path,
            output_path=fit_eval_out,
        )
        fit_eval_path = fit_eval_out

    # ---- Step 5b: Resume ----------------------------------------------------
    if mode in ("all", "resume"):
        print(f"\n  [5a/7] Generating resume prompt  →  {Path(base_output).name}")
        resume_out = str(OUTPUT_DIR / f"_tmp-resume-{slug}.md")
        run_generate(
            jd_path=jd_path,
            role=chosen_role,
            mode="resume",
            parsed_jd_path=parsed_jd_path,
            scores_path=scores_path,
            output_path=resume_out,
            use_bullet_bank=True,
        )

    # ---- Step 5c: Cover letter ----------------------------------------------
    if mode == "all":
        print(f"\n  [5b/7] Generating cover letter prompt  →  {Path(base_output).name}")
        cl_out = str(OUTPUT_DIR / f"_tmp-cover-letter-{slug}.md")
        run_generate(
            jd_path=jd_path,
            role=chosen_role,
            mode="cover-letter",
            parsed_jd_path=parsed_jd_path,
            scores_path=scores_path,
            output_path=cl_out,
            fit_eval_path=fit_eval_path,
            use_paragraph_bank=True,
        )

    # ---- Step 5d: Merge all prompt files into one output --------------------
    print(f"\n  [5c/7] Assembling prompts → {base_output}")
    combined = []
    combined.append(f"# Application: {company} — {role_title}")
    combined.append(f"**Date evaluated:** {date.today()}")
    combined.append(f"**Pre-score estimate:** {fit_estimate}/10")
    combined.append(f"**Role template used:** {chosen_role}")
    combined.append("")
    combined.append("---")
    combined.append("")

    tmp_files = []
    if mode in ("all", "fit-only", "resume") and fit_eval_path:
        combined.append("## FIT EVALUATION PROMPT\n")
        tmp_files.append(fit_eval_path)
        combined.append(Path(fit_eval_path).read_text(encoding="utf-8"))
        combined.append("\n---\n")
    if mode in ("all", "resume"):
        resume_f = str(OUTPUT_DIR / f"_tmp-resume-{slug}.md")
        if Path(resume_f).exists():
            combined.append("## RESUME PROMPT\n")
            tmp_files.append(resume_f)
            combined.append(Path(resume_f).read_text(encoding="utf-8"))
            combined.append("\n---\n")
    if mode == "all":
        cl_f = str(OUTPUT_DIR / f"_tmp-cover-letter-{slug}.md")
        if Path(cl_f).exists():
            combined.append("## COVER LETTER PROMPT\n")
            tmp_files.append(cl_f)
            combined.append(Path(cl_f).read_text(encoding="utf-8"))

    Path(base_output).write_text("\n".join(combined), encoding="utf-8")
    print(f"       Written: {base_output}")

    # Clean up temp files
    for tf in tmp_files:
        try:
            Path(tf).unlink()
        except Exception:
            pass

    # ---- Step 6: Add to tracker ---------------------------------------------
    rec = f"Pre-score {fit_estimate}/10"
    status = "applied" if fit_estimate >= 6.5 else "skipped"
    if not args.no_interact:
        ans = input(f"\n  [6/7] Add to tracker as [{status}]? [y/n/status]: ").strip().lower()
        if ans and ans not in ("y", "yes"):
            if ans in ("n", "no"):
                status = None
            elif ans in ("applied", "interviewing", "offer", "rejected", "ghosted", "skipped",
                         "pending_application", "pending_evaluation"):
                status = ans
            else:
                status = None

    if status:
        add_to_tracker(company, role_title, fit_estimate, rec,
                       str(Path(base_output).relative_to(ROOT)).replace("\\", "/"),
                       status)

    # ---- Step 7: Sync gaps to skill-development.yaml ------------------------
    print(f"  [7/7] Scanning output for skill gaps...")
    n_gaps = sync_gaps_to_skill_development(Path(base_output), company, role_title)
    if n_gaps:
        print(f"       Appended {n_gaps} gap(s) to portfolio/skill-development.yaml")
    else:
        print(f"       No gap patterns detected in output.")

    print()
    print(f"  Done! Output: {base_output}")
    print(f"  View tracker: python scripts/tracker.py --status")
    print()


if __name__ == "__main__":
    main()
