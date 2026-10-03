"""Snapshot helpers for scraper-owned HTML and CSV artifacts."""

from typing import TypedDict

HTML_SNAPSHOT_TERMS = (
    "artificial intelligence",
    "llm",
    "large language model",
    "generative ai",
    "genai",
    "machine learning",
    "deep learning",
    "nlp",
    "computer vision",
    "neural network",
    "langchain",
    "langgraph",
    "rag",
    "retrieval augmented generation",
    "pytorch",
    "tensorflow",
    "keras",
    "scikit-learn",
    "data science",
    "chatgpt",
    "ai agent",
    "mcp",
    "python",
    "fastapi",
    "django",
    "flask",
    "pydantic",
    "sqlalchemy",
    "backend",
    "backend engineer",
    "software engineer",
    "software developer",
    "full stack",
    "api",
    "rest",
    "microservices",
    "graphql",
    "grpc",
    "event-driven",
    "kafka",
    "docker",
    "kubernetes",
    "aws",
    "azure",
    "gcp",
    "terraform",
    "platform engineer",
    "etl",
    "airflow",
    "spark",
)

SNAPSHOT_CSV_FIELDS = (
    "job_number",
    "job_url",
    "title",
    "comments",
    "requirements",
    "follow_up",
    "highlight",
    "applied",
    "contact",
    "application_comments",
    "job_date",
    "salary",
    "position",
    "advertiser",
    "location",
    "work_type",
    "expired",
    "updated_at",
    "search_terms",
)


class ScraperState(TypedDict):
    snapshot_id: str
    search_term: str
    url_index: int
    page_number: int


def generate_snapshot_id(now=None):
    import datetime as _datetime

    current = now or _datetime.datetime.now(_datetime.UTC)
    return current.strftime("%Y%m%dT%H%M%SZ")


def serialize_search_terms(terms: list[str] | tuple[str, ...] | set[str]) -> str:
    ordered_terms: list[str] = []
    seen: set[str] = set()

    for term in terms:
        cleaned_term = term.strip() if term else ""
        if cleaned_term and cleaned_term not in seen:
            seen.add(cleaned_term)
            ordered_terms.append(cleaned_term)

    return " | ".join(ordered_terms)


def format_csv_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def normalize_csv_row(row) -> dict[str, str]:
    normalized = {field: "" for field in SNAPSHOT_CSV_FIELDS}
    for key, value in row.items():
        if key in normalized:
            normalized[key] = format_csv_value(value)
    return normalized


class ScraperSnapshotManager:
    def __init__(
        self,
        snapshot_root: object = "job_metadata",
        state_path: object = "scraper_state.csv",
    ):
        from pathlib import Path as _Path

        self.snapshot_root = _Path(str(snapshot_root))
        self.state_path = _Path(str(state_path))
        self.snapshot_id: str | None = None

    @property
    def snapshot_dir(self):
        from pathlib import Path as _Path

        if self.snapshot_id is None:
            raise RuntimeError(
                "Snapshot directory requested before snapshot_id was initialized."
            )
        return _Path(self.snapshot_root) / self.snapshot_id

    def ensure_snapshot(self, snapshot_id: str | None = None) -> str:
        if snapshot_id:
            self.snapshot_id = snapshot_id
        elif self.snapshot_id is None:
            self.snapshot_id = generate_snapshot_id()

        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        assert self.snapshot_id is not None
        return self.snapshot_id

    def save_state(self, search_term, url_index, page_number):
        import csv as _csv
        import tempfile as _tempfile

        snapshot_id = self.ensure_snapshot()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with _tempfile.NamedTemporaryFile(
            "w",
            delete=False,
            newline="",
            encoding="utf-8",
            dir=str(self.state_path.parent),
        ) as temp_file:
            temp_file.write(
                "# format: snapshot_id, search_term, url_index (0=remote, 1=all-melbourne), page_number (1-indexed)\n"
            )
            writer = _csv.writer(temp_file)
            writer.writerow([snapshot_id, search_term, url_index, page_number])
            temp_name = temp_file.name

        from pathlib import Path as _Path

        _Path(temp_name).replace(self.state_path)

    def load_state(self) -> ScraperState | None:
        import csv as _csv

        try:
            with self.state_path.open(encoding="utf-8") as file:
                reader = _csv.reader(row for row in file if not row.startswith("#"))
                for row in reader:
                    if len(row) >= 4 and row[0].strip():
                        return {
                            "snapshot_id": row[0],
                            "search_term": row[1],
                            "url_index": int(row[2]),
                            "page_number": int(row[3]),
                        }
                    if row:
                        raise ValueError(
                            f"Invalid scraper_state.csv at {self.state_path}: missing snapshot_id; delete the file or restore a valid state before resuming."
                        )
        except FileNotFoundError:
            return None
        except ValueError:
            raise
        except Exception as exception:
            raise ValueError(
                f"Invalid scraper_state.csv at {self.state_path}: {exception}"
            ) from exception
        return None

    def clear_state(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with self.state_path.open("w", newline="", encoding="utf-8"):
            pass

    def write_job_snapshot(self, job_number, soup, csv_row):
        self.ensure_snapshot()
        output_html = self.snapshot_dir / f"{job_number}.html"
        output_csv = self.snapshot_dir / "combined_job_search_results.csv"

        created_html = not output_html.exists()
        if created_html:
            output_html.write_text(str(soup), encoding="utf-8")
        try:
            self.upsert_csv_row(output_csv, csv_row)
        except Exception:
            if created_html and output_html.exists():
                output_html.unlink()
            raise

    def upsert_csv_row(self, csv_path, row):
        import csv as _csv
        import tempfile as _tempfile

        normalized_row = normalize_csv_row(row)
        existing_rows = {}

        if csv_path.exists():
            with csv_path.open(encoding="utf-8", newline="") as file:
                reader = _csv.DictReader(file)
                for existing_row in reader:
                    job_number = (existing_row.get("job_number") or "").strip()
                    if job_number:
                        existing_rows[job_number] = {
                            field: existing_row.get(field, "")
                            for field in SNAPSHOT_CSV_FIELDS
                        }

        job_number = normalized_row["job_number"]
        existing_rows[job_number] = normalized_row

        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with _tempfile.NamedTemporaryFile(
            "w", delete=False, newline="", encoding="utf-8", dir=str(csv_path.parent)
        ) as temp_file:
            writer = _csv.DictWriter(temp_file, fieldnames=list(SNAPSHOT_CSV_FIELDS))
            writer.writeheader()
            for existing_row in existing_rows.values():
                writer.writerow(existing_row)
            temp_name = temp_file.name

        from pathlib import Path as _Path

        _Path(temp_name).replace(csv_path)
