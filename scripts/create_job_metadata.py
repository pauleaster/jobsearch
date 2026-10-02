"""Create HTML snapshots for jobs listed in the latest combined_job_search_results.csv.

For each CSV row, this script reads job_url and job_number, fetches the job page
using scraper_module NetworkHandler, and writes the parsed HTML to:
    ./job_metadata/<snapshot_id>/<job_number>.html

The snapshot_id is taken from the most recent backend export run and is shared
between the copied CSV and the downloaded HTML files.
"""

from __future__ import annotations

import csv
import re
import shutil
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scraper_module.handlers import NetworkHandler


BACKEND_EXPORT_ROOT = Path(
    r"C:\Users\paulj\repos\dotnet\Jobsearch_backend_combined\Jobsearch_backend_py"
)
BACKEND_RUNS_ROOT = BACKEND_EXPORT_ROOT / "runs"
SNAPSHOT_DIR_PATTERN = re.compile(r"^\d{8}T\d{6}Z$")


def extract_job_number(job_url: str) -> str | None:
    """Extract a job number from a URL like https://.../job/12345678."""
    match = re.search(r"/job/(\d+)", job_url)
    return match.group(1) if match else None


def iter_csv_rows(csv_path: Path):
    """Yield CSV rows as dictionaries."""
    with csv_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            yield row


def find_latest_snapshot_dir(runs_root: Path) -> Path:
    """Return the most recent timestamped snapshot directory."""
    snapshot_dirs = [
        child
        for child in runs_root.iterdir()
        if child.is_dir() and SNAPSHOT_DIR_PATTERN.fullmatch(child.name)
    ]
    if not snapshot_dirs:
        raise FileNotFoundError(f"No snapshot directories found in: {runs_root}")
    return max(snapshot_dirs, key=lambda path: path.name)


def prepare_run_paths(repo_root: Path) -> tuple[Path, Path, Path]:
    """Return the source CSV path, run snapshot id, and output directory."""
    snapshot_dir = find_latest_snapshot_dir(BACKEND_RUNS_ROOT)
    snapshot_id = snapshot_dir.name
    csv_path = snapshot_dir / "combined_job_search_results.csv"
    output_dir = repo_root / "job_metadata" / snapshot_id
    return csv_path, snapshot_id, output_dir


def main() -> None:
    repo_root = REPO_ROOT
    csv_path, _snapshot_id, output_dir = prepare_run_paths(repo_root)

    if output_dir.exists():
        raise FileExistsError(
            f"Snapshot directory already exists and will not be overwritten: {output_dir}"
        )

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    output_dir.mkdir(parents=True, exist_ok=False)
    copied_csv_path = output_dir / "combined_job_search_results.csv"
    shutil.copy2(csv_path, copied_csv_path)

    rows = list(iter_csv_rows(copied_csv_path))
    if not rows:
        print("No rows found in CSV.")
        return

    first_url = next((r.get("job_url", "").strip() for r in rows if r.get("job_url")), None)
    if not first_url:
        print("No valid job_url values found in CSV.")
        return

    handler = NetworkHandler(first_url)
    success_count = 0
    failed_count = 0

    try:
        for index, row in enumerate(rows, start=1):
            job_url = (row.get("job_url") or "").strip()
            if not job_url:
                print(f"[{index}] Missing job_url, skipping.")
                failed_count += 1
                continue

            job_number = (row.get("job_number") or "").strip()
            if not job_number:
                job_number = extract_job_number(job_url) or ""

            if not job_number:
                print(f"[{index}] Could not determine job_number for URL: {job_url}")
                failed_count += 1
                continue

            # Use the scraper module's standard delay between successive URL reads.
            soup = handler.get_soup(job_url)
            if soup is None:
                print(f"[{index}] Failed to load URL: {job_url}")
                failed_count += 1
                continue

            output_path = output_dir / f"{job_number}.html"
            output_path.write_text(str(soup), encoding="utf-8")
            print(f"[{index}] Saved {output_path.name}")
            success_count += 1
    finally:
        handler.close()

    print(f"Done. Saved: {success_count}, Failed: {failed_count}")


if __name__ == "__main__":
    main()
