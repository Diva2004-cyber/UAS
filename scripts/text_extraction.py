"""Extract normalized text records from acquired document evidence.

The extractor reads the Phase 3 metadata log, processes working copies, and
writes a fixed-schema `dataset_processed/extracted_text.csv` plus an extraction
failure table. Large dataset shards are sampled by default for a realistic UAS
MVP while preserving traceability to raw evidence.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import pyarrow.parquet as pq


DEFAULT_MAX_RECORDS_PER_FILE = 200
TEXT_COLUMN_CANDIDATES = [
    "text",
    "response",
    "answer",
    "output",
    "generated_text",
    "content",
    "article",
    "abstract",
    "essay",
    "completion",
    "document",
]

OUTPUT_FIELDS = [
    "evidence_id",
    "evidence_doc_id",
    "doc_id",
    "source_record_id",
    "domain",
    "label_doc",
    "source",
    "file_name",
    "file_type",
    "hash_sha256",
    "extraction_method",
    "text",
]

FAILURE_FIELDS = [
    "evidence_id",
    "evidence_doc_id",
    "file_name",
    "file_type",
    "label_doc",
    "error_type",
    "error_message",
]


def parse_args() -> argparse.Namespace:
    default_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Extract text from acquired document evidence.")
    parser.add_argument("--project-root", type=Path, default=default_root)
    parser.add_argument(
        "--metadata",
        type=Path,
        default=None,
        help="Metadata CSV from Phase 3. Defaults to evidence_acquired/metadata_log.csv.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Extraction output CSV. Defaults to dataset_processed/extracted_text.csv.",
    )
    parser.add_argument(
        "--failures",
        type=Path,
        default=None,
        help="Failure output CSV. Defaults to results/tables/extraction_failures.csv.",
    )
    parser.add_argument(
        "--max-records-per-file",
        type=int,
        default=DEFAULT_MAX_RECORDS_PER_FILE,
        help="Maximum extracted records per evidence file. Use 0 for no cap.",
    )
    return parser.parse_args()


def powershell_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def run_powershell(script: str, input_text: str | None = None) -> None:
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        input=input_text,
        text=True,
        encoding="utf-8",
        check=True,
    )


def ensure_directory(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
        return
    except FileNotFoundError:
        run_powershell(
            f"New-Item -ItemType Directory -Force -Path {powershell_quote(str(path))} | Out-Null"
        )


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fieldnames: list[str]) -> None:
    ensure_directory(path.parent)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    script = (
        "$content = [Console]::In.ReadToEnd(); "
        f"Set-Content -Path {powershell_quote(str(path))} -Value $content -Encoding UTF8"
    )
    run_powershell(script, buffer.getvalue())


def clean_extracted_text(text: Any) -> str:
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    text = text.replace("\ufeff", " ")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", text)
    return text.strip()


def recursive_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (int, float, bool)):
        return []
    if isinstance(value, list):
        strings: list[str] = []
        for item in value:
            strings.extend(recursive_strings(item))
        return strings
    if isinstance(value, dict):
        strings = []
        for item in value.values():
            strings.extend(recursive_strings(item))
        return strings
    return []


def text_from_messages(messages: Any) -> str:
    if not isinstance(messages, list):
        return ""
    assistant_parts = []
    fallback_parts = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        content = clean_extracted_text(message.get("content"))
        if not content:
            continue
        role = str(message.get("role", "")).lower()
        if role in {"assistant", "model", "chatgpt"}:
            assistant_parts.append(content)
        elif role != "system":
            fallback_parts.append(content)
    return "\n\n".join(assistant_parts or fallback_parts)


def text_from_object(obj: Any) -> tuple[str, str]:
    if isinstance(obj, dict):
        if "messages" in obj:
            text = text_from_messages(obj["messages"])
            if text:
                return text, "messages_assistant_content"

        for key in TEXT_COLUMN_CANDIDATES:
            if key in obj and clean_extracted_text(obj[key]):
                return clean_extracted_text(obj[key]), f"json_key:{key}"

        strings = [clean_extracted_text(part) for part in recursive_strings(obj)]
        strings = [part for part in strings if len(part) >= 20]
        return "\n\n".join(strings), "json_recursive_strings"

    if isinstance(obj, list):
        strings = [clean_extracted_text(part) for part in recursive_strings(obj)]
        strings = [part for part in strings if len(part) >= 20]
        return "\n\n".join(strings), "json_list_recursive_strings"

    return clean_extracted_text(obj), "raw_value"


def article_json_to_text(value: Any) -> str:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return clean_extracted_text(value)

    parts: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if "sentence" in node:
                parts.append(clean_extracted_text(node.get("sentence")))
            if "alternative" in node:
                parts.append(clean_extracted_text(node.get("alternative")))
            for key, child in node.items():
                if key not in {"sentence", "alternative", "title"}:
                    walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(value)
    return "\n\n".join(part for part in parts if part)


def build_row(metadata: pd.Series, record_index: int, source_record_id: str, method: str, text: str) -> dict[str, Any]:
    return {
        "evidence_id": metadata["evidence_id"],
        "evidence_doc_id": metadata["doc_id"],
        "doc_id": f"{metadata['doc_id']}-REC-{record_index:06d}",
        "source_record_id": source_record_id,
        "domain": metadata["domain"],
        "label_doc": metadata["label_doc"],
        "source": metadata["source"],
        "file_name": metadata["file_name"],
        "file_type": metadata["file_type"],
        "hash_sha256": metadata["hash_sha256"],
        "extraction_method": method,
        "text": text,
    }


def selected_text_columns(columns: Iterable[str]) -> list[str]:
    columns = list(columns)
    selected = [column for column in columns if column in TEXT_COLUMN_CANDIDATES]
    return selected or columns[: min(5, len(columns))]


def extract_jsonl(path: Path, metadata: pd.Series, limit: int) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_index, line in enumerate(handle, start=1):
            if limit and len(rows) >= limit:
                break
            if not line.strip():
                continue
            obj = json.loads(line)
            text, method = text_from_object(obj)
            text = clean_extracted_text(text)
            if text:
                rows.append(build_row(metadata, len(rows) + 1, f"line:{line_index}", method, text))
    return rows


def extract_json(path: Path, metadata: pd.Series, limit: int) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        obj = json.load(handle)
    items = obj if isinstance(obj, list) else [obj]
    rows = []
    for item_index, item in enumerate(items, start=1):
        if limit and len(rows) >= limit:
            break
        text, method = text_from_object(item)
        text = clean_extracted_text(text)
        if text:
            rows.append(build_row(metadata, len(rows) + 1, f"item:{item_index}", method, text))
    return rows


def extract_csv(path: Path, metadata: pd.Series, limit: int) -> list[dict[str, Any]]:
    rows = []
    for chunk in pd.read_csv(path, chunksize=100):
        for _, record in chunk.iterrows():
            if limit and len(rows) >= limit:
                return rows
            if "article_json" in record and pd.notna(record["article_json"]):
                text = article_json_to_text(record["article_json"])
                method = "csv_article_json"
            else:
                columns = selected_text_columns(record.index)
                text = "\n\n".join(clean_extracted_text(record[column]) for column in columns)
                method = "csv_selected_columns"
            text = clean_extracted_text(text)
            if text:
                source_record_id = f"row:{len(rows) + 1}"
                rows.append(build_row(metadata, len(rows) + 1, source_record_id, method, text))
    return rows


def extract_parquet(path: Path, metadata: pd.Series, limit: int) -> list[dict[str, Any]]:
    parquet_file = pq.ParquetFile(path)
    columns = selected_text_columns(parquet_file.schema.names)
    rows = []
    for batch in parquet_file.iter_batches(batch_size=100, columns=columns):
        frame = batch.to_pandas()
        for _, record in frame.iterrows():
            if limit and len(rows) >= limit:
                return rows
            text = "\n\n".join(clean_extracted_text(record[column]) for column in columns)
            text = clean_extracted_text(text)
            if text:
                source_record_id = f"row:{len(rows) + 1}"
                rows.append(build_row(metadata, len(rows) + 1, source_record_id, "parquet_selected_columns", text))
    return rows


def extract_file(project_root: Path, metadata: pd.Series, limit: int) -> list[dict[str, Any]]:
    path = project_root / metadata["working_copy_path"]
    file_type = str(metadata["file_type"]).lower()
    if file_type == "jsonl":
        return extract_jsonl(path, metadata, limit)
    if file_type == "json":
        return extract_json(path, metadata, limit)
    if file_type == "csv":
        return extract_csv(path, metadata, limit)
    if file_type == "parquet":
        return extract_parquet(path, metadata, limit)
    raise ValueError(f"Unsupported file type for Phase 4 extraction: {file_type}")


def failure_row(metadata: pd.Series, exc: Exception) -> dict[str, Any]:
    return {
        "evidence_id": metadata.get("evidence_id", ""),
        "evidence_doc_id": metadata.get("doc_id", ""),
        "file_name": metadata.get("file_name", ""),
        "file_type": metadata.get("file_type", ""),
        "label_doc": metadata.get("label_doc", ""),
        "error_type": type(exc).__name__,
        "error_message": str(exc),
    }


def main() -> None:
    args = parse_args()
    project_root = args.project_root.resolve()
    metadata_path = args.metadata or project_root / "evidence_acquired" / "metadata_log.csv"
    output_path = args.output or project_root / "dataset_processed" / "extracted_text.csv"
    failures_path = args.failures or project_root / "results" / "tables" / "extraction_failures.csv"

    metadata = pd.read_csv(metadata_path)
    extracted_rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for _, item in metadata.iterrows():
        try:
            rows = extract_file(project_root, item, args.max_records_per_file)
            if not rows:
                raise ValueError("No extractable text records found.")
            extracted_rows.extend(rows)
        except Exception as exc:  # Keep auditability over hard failure for one file.
            failures.append(failure_row(item, exc))

    write_csv(output_path, extracted_rows, OUTPUT_FIELDS)
    write_csv(failures_path, failures, FAILURE_FIELDS)
    print(f"Extracted text records: {len(extracted_rows)}")
    print(f"Extraction failures: {len(failures)}")
    print(f"Wrote {output_path.relative_to(project_root)}")
    print(f"Wrote {failures_path.relative_to(project_root)}")


if __name__ == "__main__":
    main()
