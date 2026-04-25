"""Evidence intake for document-only forensic text analysis.

This script registers raw document evidence, computes SHA-256 hashes, creates
working copies, and writes fixed-schema CSV manifests for later phases.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


HASH_ALGORITHM = "sha256"
BUFFER_SIZE = 1024 * 1024
SUPPORTED_EXTENSIONS = {".csv", ".json", ".jsonl", ".parquet", ".txt", ".docx", ".pdf"}
CLASS_FOLDER_TO_LABEL = {
    "human": "human",
    "ai-generated": "ai_generated",
    "ai_generated": "ai_generated",
    "mix": "mixed",
    "mixed": "mixed",
}

HASH_MANIFEST_FIELDS = [
    "evidence_id",
    "doc_id",
    "domain",
    "label_doc",
    "file_name",
    "file_type",
    "file_size",
    "hash_algorithm",
    "hash_sha256",
    "copied_hash_sha256",
    "hash_match",
    "original_path",
    "working_copy_path",
]

METADATA_FIELDS = [
    "evidence_id",
    "doc_id",
    "file_name",
    "file_type",
    "domain",
    "source",
    "acquisition_date",
    "file_size",
    "hash_sha256",
    "label_doc",
    "notes",
    "original_path",
    "working_copy_path",
]


@dataclass(frozen=True)
class EvidenceFile:
    path: Path
    relative_to_raw: Path
    class_folder: str
    label_doc: str


def parse_args() -> argparse.Namespace:
    default_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Register document evidence, compute hashes, and create working copies."
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=default_root,
        help="Project root directory. Defaults to the parent of scripts/.",
    )
    parser.add_argument(
        "--raw-documents",
        type=Path,
        default=None,
        help="Raw document evidence directory. Defaults to evidence_raw/documents.",
    )
    parser.add_argument(
        "--copied-files",
        type=Path,
        default=None,
        help="Working copy output directory. Defaults to evidence_acquired/copied_files.",
    )
    return parser.parse_args()


def normalize_path(path: Path) -> str:
    return path.as_posix()


def discover_evidence(raw_documents: Path, project_root: Path) -> list[EvidenceFile]:
    evidence_files: list[EvidenceFile] = []
    for path in raw_documents.rglob("*"):
        if not path.is_file() or path.name == ".gitkeep" or path.name.startswith("."):
            continue
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        relative_to_documents = path.relative_to(raw_documents)
        parts = relative_to_documents.parts
        if not parts:
            continue

        class_folder = parts[0]
        label_doc = CLASS_FOLDER_TO_LABEL.get(class_folder)
        if label_doc is None:
            continue

        evidence_files.append(
            EvidenceFile(
                path=path,
                relative_to_raw=path.relative_to(project_root / "evidence_raw"),
                class_folder=class_folder,
                label_doc=label_doc,
            )
        )

    return sorted(evidence_files, key=lambda item: normalize_path(item.relative_to_raw).lower())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(BUFFER_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def powershell_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def run_powershell(script: str) -> None:
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        check=True,
    )


def write_text_with_powershell(path: Path, text: str) -> None:
    script = f"$input | Set-Content -Path {powershell_quote(str(path))} -Encoding UTF8"
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        input=text,
        text=True,
        check=True,
    )


def ensure_directory(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
        return
    except FileNotFoundError:
        if os.name != "nt":
            raise

    run_powershell(
        f"New-Item -ItemType Directory -Force -Path {powershell_quote(str(path))} | Out-Null"
    )


def copy_file(source: Path, destination: Path) -> None:
    ensure_directory(destination.parent)
    run_powershell(
        "Copy-Item -LiteralPath "
        f"{powershell_quote(str(source))} -Destination {powershell_quote(str(destination))} -Force"
    )


def write_csv(path: Path, rows: Iterable[dict[str, object]], fieldnames: list[str]) -> None:
    ensure_directory(path.parent)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    write_text_with_powershell(path, buffer.getvalue())


def register_evidence(project_root: Path, raw_documents: Path, copied_files: Path) -> tuple[int, int]:
    evidence_items = discover_evidence(raw_documents, project_root)
    acquisition_date = datetime.now().astimezone().isoformat(timespec="seconds")
    hash_rows: list[dict[str, object]] = []
    metadata_rows: list[dict[str, object]] = []

    for index, item in enumerate(evidence_items, start=1):
        evidence_id = f"EVD-{index:06d}"
        doc_id = f"DOC-{index:06d}"
        working_copy = copied_files / item.relative_to_raw
        hash_sha256 = sha256_file(item.path)
        copy_file(item.path, working_copy)
        copied_hash_sha256 = sha256_file(working_copy)
        hash_match = hash_sha256 == copied_hash_sha256
        file_size = item.path.stat().st_size
        file_type = item.path.suffix.lower().lstrip(".")
        original_path = normalize_path(item.path.relative_to(project_root))
        working_copy_path = normalize_path(working_copy.relative_to(project_root))

        hash_rows.append(
            {
                "evidence_id": evidence_id,
                "doc_id": doc_id,
                "domain": "document",
                "label_doc": item.label_doc,
                "file_name": item.path.name,
                "file_type": file_type,
                "file_size": file_size,
                "hash_algorithm": HASH_ALGORITHM,
                "hash_sha256": hash_sha256,
                "copied_hash_sha256": copied_hash_sha256,
                "hash_match": hash_match,
                "original_path": original_path,
                "working_copy_path": working_copy_path,
            }
        )

        metadata_rows.append(
            {
                "evidence_id": evidence_id,
                "doc_id": doc_id,
                "file_name": item.path.name,
                "file_type": file_type,
                "domain": "document",
                "source": f"manual_document_dataset/{item.class_folder}",
                "acquisition_date": acquisition_date,
                "file_size": file_size,
                "hash_sha256": hash_sha256,
                "label_doc": item.label_doc,
                "notes": "Registered from document-only raw evidence; master evidence preserved.",
                "original_path": original_path,
                "working_copy_path": working_copy_path,
            }
        )

    evidence_acquired = project_root / "evidence_acquired"
    write_csv(evidence_acquired / "hash_manifest.csv", hash_rows, HASH_MANIFEST_FIELDS)
    write_csv(evidence_acquired / "metadata_log.csv", metadata_rows, METADATA_FIELDS)
    match_count = sum(1 for row in hash_rows if row["hash_match"] is True)
    return len(evidence_items), match_count


def main() -> None:
    args = parse_args()
    project_root = args.project_root.resolve()
    raw_documents = (
        args.raw_documents.resolve()
        if args.raw_documents
        else project_root / "evidence_raw" / "documents"
    )
    copied_files = (
        args.copied_files.resolve()
        if args.copied_files
        else project_root / "evidence_acquired" / "copied_files"
    )

    if not raw_documents.exists():
        raise FileNotFoundError(f"Raw document evidence directory not found: {raw_documents}")

    total, matched = register_evidence(project_root, raw_documents, copied_files)
    print(f"Registered evidence files: {total}")
    print(f"Hash matches after copy: {matched}/{total}")
    print("Wrote evidence_acquired/hash_manifest.csv")
    print("Wrote evidence_acquired/metadata_log.csv")


if __name__ == "__main__":
    main()
