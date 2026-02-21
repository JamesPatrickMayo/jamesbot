#!/usr/bin/env python3
"""
Application Tracker — manage output/tracker.yaml.

Commands:
    --add           Append a new application entry (interactive or via flags)
    --update        Update status / notes on an existing entry
    --status        Print a formatted summary table to terminal
    --export-csv    Write output/tracker.csv
    --scan-outputs  Scan output/application-*.md and import any missing entries

Usage examples:
    python scripts/tracker.py --status
    python scripts/tracker.py --add --company "HiBob" --role "Implementation Manager" \\
        --fit 7.5 --recommendation APPLY --output-file output/application-hibob-impl-2026-02-20.md
    python scripts/tracker.py --update --company "HiBob" --status interviewing --notes "Phone screen scheduled"
    python scripts/tracker.py --export-csv
    python scripts/tracker.py --scan-outputs
"""

import argparse
import csv
import re
import sys
from datetime import date, datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
TRACKER_PATH = ROOT / "output" / "tracker.yaml"
OUTPUT_DIR = ROOT / "output"

VALID_STATUSES = {"applied", "interviewing", "offer", "rejected", "ghosted", "skipped", "pending_application", "pending_evaluation"}


# ---- YAML helpers -----------------------------------------------------------

def load_tracker() -> dict:
    if not TRACKER_PATH.exists():
        return {"applications": [], "metadata": {"last_updated": str(date.today())}}
    with open(TRACKER_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if "applications" not in data:
        data["applications"] = []
    return data


def save_tracker(data: dict) -> None:
    data["metadata"] = {"last_updated": str(date.today())}
    TRACKER_PATH.parent.mkdir(exist_ok=True)
    with open(TRACKER_PATH, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


# ---- Entry helpers ----------------------------------------------------------

def _slug(text: str) -> str:
    """Lowercase slug for fuzzy matching."""
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def find_entry(apps: list[dict], company: str, role: str | None = None) -> int | None:
    """Return index of matching entry or None."""
    comp_slug = _slug(company)
    for i, app in enumerate(apps):
        if _slug(app.get("company", "")) == comp_slug:
            if role is None:
                return i
            if _slug(app.get("role", "")) == _slug(role):
                return i
    return None


def build_entry(
    company: str,
    role: str,
    fit_score: float | None,
    recommendation: str,
    status: str,
    output_file: str = "",
    date_evaluated: str = "",
    date_applied: str = "",
    notes: str = "",
) -> dict:
    return {
        "company": company,
        "role": role,
        "date_evaluated": date_evaluated or str(date.today()),
        "fit_score": fit_score,
        "recommendation": recommendation,
        "status": status,
        "date_applied": date_applied,
        "output_file": output_file,
        "notes": notes,
    }


# ---- Scan outputs -----------------------------------------------------------

def _parse_output_file(path: Path) -> dict | None:
    """Extract company, role, fit score, and recommendation from an application .md file."""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None

    # Fit score — try a few patterns seen in output files
    fit = None
    for pattern in [
        r"\*\*Overall Fit Score:\*\*\s*([\d.]+)/10",
        r"Overall Fit Score.*?\*\*([\d.]+)/10\*\*",
        r"Fit Score.*?([\d.]+)/10",
        r"Confidence Score:\s*([\d.]+)/10",
    ]:
        m = re.search(pattern, text)
        if m:
            try:
                fit = float(m.group(1))
            except ValueError:
                pass
            break

    # Recommendation
    rec = ""
    for pattern in [
        r"\*\*Recommendation:\*\*\s*(.+)",
        r"Recommendation:\*\*\s*(.+)",
        r"^##\s*RECOMMENDATION:\s*(.+)",
        r"^\*\*Recommendation:\s*(.+)",
    ]:
        m = re.search(pattern, text, re.MULTILINE)
        if m:
            rec = m.group(1).strip().rstrip("*").strip()
            break

    # Derive status from recommendation
    rec_upper = rec.upper()
    if "SKIP" in rec_upper:
        status = "skipped"
    elif "APPLY" in rec_upper or "INVESTIGATE" in rec_upper:
        status = "applied"
    else:
        status = "pending_application"

    # Extract company and role from filename: application-{company}-{role}-{date}.md
    stem = path.stem  # e.g. application-merge-solutions-engineer-2026-02-20
    stem = re.sub(r"^application-", "", stem)
    # Strip trailing date
    stem = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", stem)
    # Infer company (first token) and role (rest)
    parts = stem.split("-", 1)
    company = parts[0].title() if parts else "Unknown"
    role = parts[1].replace("-", " ").title() if len(parts) > 1 else stem

    # Extract evaluation date from filename
    date_m = re.search(r"(\d{4}-\d{2}-\d{2})", path.stem)
    eval_date = date_m.group(1) if date_m else str(date.today())

    return build_entry(
        company=company,
        role=role,
        fit_score=fit,
        recommendation=rec,
        status=status,
        output_file=str(path.relative_to(ROOT)).replace("\\", "/"),
        date_evaluated=eval_date,
    )


def scan_outputs(data: dict, dry_run: bool = False) -> int:
    """Scan output/application-*.md and add any missing entries to tracker."""
    apps = data["applications"]
    added = 0

    for md_path in sorted(OUTPUT_DIR.glob("application-*.md")):
        entry = _parse_output_file(md_path)
        if not entry:
            continue
        idx = find_entry(apps, entry["company"], entry["role"])
        if idx is not None:
            continue  # already tracked
        if not dry_run:
            apps.append(entry)
        print(f"  {'[DRY RUN] ' if dry_run else ''}Added: {entry['company']} — {entry['role']}  (fit: {entry['fit_score']}, {entry['status']})")
        added += 1

    return added


# ---- CLI commands -----------------------------------------------------------

def cmd_add(args, data: dict) -> None:
    apps = data["applications"]

    # Interactive fallback if required flags missing
    company = args.company or input("Company name: ").strip()
    role = args.role or input("Role: ").strip()
    fit = args.fit
    if fit is None:
        val = input("Fit score (e.g. 7.5, leave blank to skip): ").strip()
        fit = float(val) if val else None
    rec = args.recommendation or input("Recommendation (APPLY/SKIP/etc.): ").strip()
    status = args.app_status or "applied"
    output_file = args.output_file or ""
    notes = args.notes or ""

    idx = find_entry(apps, company, role)
    if idx is not None:
        print(f"Warning: Entry for {company} — {role} already exists. Use --update to modify.")
        return

    entry = build_entry(
        company=company,
        role=role,
        fit_score=fit,
        recommendation=rec,
        status=status,
        output_file=output_file,
        notes=notes,
    )
    apps.append(entry)
    save_tracker(data)
    print(f"Added: {company} — {role}  [{status}]")


def cmd_update(args, data: dict) -> None:
    apps = data["applications"]
    if not args.company:
        print("Error: --company is required for --update")
        sys.exit(1)

    idx = find_entry(apps, args.company, args.role)
    if idx is None:
        print(f"Error: No entry found for company '{args.company}'" +
              (f" role '{args.role}'" if args.role else ""))
        sys.exit(1)

    entry = apps[idx]
    if args.app_status:
        if args.app_status not in VALID_STATUSES:
            print(f"Invalid status '{args.app_status}'. Valid: {', '.join(sorted(VALID_STATUSES))}")
            sys.exit(1)
        entry["status"] = args.app_status
    if args.notes:
        entry["notes"] = args.notes
    if args.fit:
        entry["fit_score"] = args.fit
    if args.date_applied:
        entry["date_applied"] = args.date_applied

    save_tracker(data)
    print(f"Updated: {entry['company']} — {entry['role']}  [{entry['status']}]")


def cmd_status(data: dict) -> None:
    apps = data["applications"]
    if not apps:
        print("No applications tracked yet.")
        return

    # Group by status
    groups: dict[str, list[dict]] = {}
    for app in apps:
        s = app.get("status", "unknown")
        groups.setdefault(s, []).append(app)

    STATUS_ORDER = ["applied", "interviewing", "offer", "pending_application",
                    "pending_evaluation", "rejected", "ghosted", "skipped"]

    COL_W = {"company": 18, "role": 32, "fit": 6, "rec": 22, "status": 20, "notes": 28}
    header = (
        f"{'Company':<{COL_W['company']}} "
        f"{'Role':<{COL_W['role']}} "
        f"{'Fit':>{COL_W['fit']}} "
        f"{'Recommendation':<{COL_W['rec']}} "
        f"{'Status':<{COL_W['status']}} "
        f"{'Notes':<{COL_W['notes']}}"
    )
    divider = "-" * len(header)

    print(f"\n{'='*len(header)}")
    print(f"  APPLICATION TRACKER  ({len(apps)} total | last updated: {data.get('metadata', {}).get('last_updated', '?')})")
    print(f"{'='*len(header)}\n")

    for status_key in STATUS_ORDER:
        group = groups.get(status_key, [])
        if not group:
            continue
        label = status_key.upper().replace("_", " ")
        print(f"  [{label}] ({len(group)})")
        print(f"  {divider}")
        print(f"  {header}")
        print(f"  {divider}")
        for app in sorted(group, key=lambda x: x.get("date_evaluated", ""), reverse=True):
            company = str(app.get("company", ""))[:COL_W["company"]]
            role = str(app.get("role", ""))[:COL_W["role"]]
            fit = str(app.get("fit_score", "?"))
            rec = str(app.get("recommendation", ""))[:COL_W["rec"]]
            notes = str(app.get("notes", ""))[:COL_W["notes"]]
            print(
                f"  {company:<{COL_W['company']}} "
                f"{role:<{COL_W['role']}} "
                f"{fit:>{COL_W['fit']}} "
                f"{rec:<{COL_W['rec']}} "
                f"{status_key:<{COL_W['status']}} "
                f"{notes:<{COL_W['notes']}}"
            )
        print()

    # Summary counts
    print(f"  Summary:")
    for s in STATUS_ORDER:
        count = len(groups.get(s, []))
        if count:
            print(f"    {s.replace('_', ' '):25} {count}")
    print()


def cmd_export_csv(data: dict) -> None:
    apps = data["applications"]
    if not apps:
        print("No applications to export.")
        return

    csv_path = ROOT / "output" / "tracker.csv"
    fieldnames = ["company", "role", "date_evaluated", "fit_score", "recommendation",
                  "status", "date_applied", "output_file", "notes"]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for app in sorted(apps, key=lambda x: x.get("date_evaluated", ""), reverse=True):
            writer.writerow(app)

    print(f"Exported {len(apps)} applications to: {csv_path}")


def cmd_scan_outputs(data: dict) -> None:
    print("Scanning output/ for untracked application files...")
    added = scan_outputs(data)
    if added:
        save_tracker(data)
        print(f"\nAdded {added} new entries to tracker.")
    else:
        print("No new entries found — tracker is up to date.")


# ---- Main -------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Manage the application tracker (output/tracker.yaml)"
    )
    parser.add_argument("--add", action="store_true", help="Add a new entry")
    parser.add_argument("--update", action="store_true", help="Update an existing entry")
    parser.add_argument("--status", action="store_true", help="Print status table")
    parser.add_argument("--export-csv", action="store_true", dest="export_csv",
                        help="Export to output/tracker.csv")
    parser.add_argument("--scan-outputs", action="store_true", dest="scan_outputs",
                        help="Scan output/ directory and import missing entries")

    # Entry fields
    parser.add_argument("--company", help="Company name")
    parser.add_argument("--role", help="Role title")
    parser.add_argument("--fit", type=float, help="Fit score (0–10)")
    parser.add_argument("--recommendation", help="LLM recommendation string")
    parser.add_argument("--app-status", dest="app_status",
                        help=f"Application status: {', '.join(sorted(VALID_STATUSES))}")
    parser.add_argument("--output-file", dest="output_file",
                        help="Relative path to output .md file")
    parser.add_argument("--date-applied", dest="date_applied",
                        help="Date applied (YYYY-MM-DD)")
    parser.add_argument("--notes", help="Free-text notes")
    args = parser.parse_args()

    data = load_tracker()

    if args.add:
        cmd_add(args, data)
    elif args.update:
        cmd_update(args, data)
    elif args.status:
        cmd_status(data)
    elif args.export_csv:
        cmd_export_csv(data)
    elif args.scan_outputs:
        cmd_scan_outputs(data)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
