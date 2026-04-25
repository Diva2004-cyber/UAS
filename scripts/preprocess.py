"""Minimal preprocessing for extracted forensic text evidence.

Preprocessing intentionally preserves casing, punctuation, and stylistic cues.
It removes control characters, normalizes whitespace, and records basic counts
used by later segmentation and feature extraction phases.
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
from pathlib import Path
from typing import Any, Iterable, Iterator

import pandas as pd


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
    "clean_text",
    "char_count",
    "token_count",
    "sentence_count",
    "preprocessing_notes",
]

SEGMENT_FIELDS = [
    "evidence_id",
    "evidence_doc_id",
    "doc_id",
    "segment_id",
    "segment_type",
    "segment_index",
    "start_index",
    "end_index",
    "segment_text",
    "segment_char_count",
    "segment_token_count",
    "segment_sentence_count",
    "domain",
    "label_doc",
    "segment_label",
    "tampering_type",
    "annotation_source",
    "hash_sha256",
    "file_name",
    "source_record_id",
]

ANNOTATION_FIELDS = [
    "evidence_id",
    "evidence_doc_id",
    "doc_id",
    "segment_id",
    "segment_type",
    "start_index",
    "end_index",
    "label_doc",
    "segment_label",
    "tampering_type",
    "annotation_source",
]


def parse_args() -> argparse.Namespace:
    default_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Apply minimal preprocessing or generate document segments."
    )
    parser.add_argument("--project-root", type=Path, default=default_root)
    parser.add_argument(
        "--mode",
        choices=["preprocess", "segment"],
        default="preprocess",
        help="Run minimal preprocessing or Phase 5 segmentation.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Input CSV. Defaults depend on --mode.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output CSV. Defaults depend on --mode.",
    )
    parser.add_argument(
        "--annotations-output",
        type=Path,
        default=None,
        help="Segment annotation CSV. Defaults to dataset_processed/segment_annotations.csv.",
    )
    parser.add_argument(
        "--window-size",
        type=int,
        default=75,
        help="Sliding-window segment size in tokens.",
    )
    parser.add_argument(
        "--window-stride",
        type=int,
        default=50,
        help="Sliding-window stride in tokens.",
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
    script = (
        "$writer = [System.IO.StreamWriter]::new("
        f"{powershell_quote(str(path))}, "
        "$false, "
        "[System.Text.UTF8Encoding]::new($false)"
        "); "
        "try { while (($line = [Console]::In.ReadLine()) -ne $null) { "
        "$writer.WriteLine($line) } } finally { $writer.Close() }"
    )
    process = subprocess.Popen(
        ["powershell", "-NoProfile", "-Command", script],
        stdin=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    if process.stdin is None:
        raise RuntimeError("Failed to open PowerShell stdin for CSV writing.")
    writer = csv.DictWriter(process.stdin, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    process.stdin.close()
    return_code = process.wait()
    if return_code != 0:
        raise subprocess.CalledProcessError(return_code, process.args)


def minimal_clean(text: Any) -> str:
    if text is None or pd.isna(text):
        return ""
    if not isinstance(text, str):
        text = str(text)
    text = text.replace("\ufeff", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def token_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def sentence_count(text: str) -> int:
    parts = [part for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    return len(parts)


def token_spans(text: str) -> list[re.Match[str]]:
    return list(re.finditer(r"\b\w+\b", text))


def sentence_spans(text: str) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    pattern = re.compile(r"[^.!?\n]+(?:[.!?]+(?=\s|$)|$)", re.MULTILINE)
    for match in pattern.finditer(text):
        segment = match.group(0).strip()
        if not segment:
            continue
        start = match.start() + len(match.group(0)) - len(match.group(0).lstrip())
        end = match.end() - len(match.group(0)) + len(match.group(0).rstrip())
        if end > start:
            spans.append((start, end, text[start:end]))
    return spans or [(0, len(text), text)] if text else []


def paragraph_spans(text: str) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    for match in re.finditer(r"\S(?:.*?)(?=\n\s*\n|$)", text, flags=re.DOTALL):
        segment = match.group(0).strip()
        if not segment:
            continue
        start = match.start() + len(match.group(0)) - len(match.group(0).lstrip())
        end = match.end() - len(match.group(0)) + len(match.group(0).rstrip())
        if end > start:
            spans.append((start, end, text[start:end]))
    return spans or [(0, len(text), text)] if text else []


def sliding_window_spans(text: str, window_size: int, stride: int) -> list[tuple[int, int, str]]:
    tokens = token_spans(text)
    if not tokens:
        return []
    window_size = max(1, window_size)
    stride = max(1, stride)
    if len(tokens) <= window_size:
        start = tokens[0].start()
        end = tokens[-1].end()
        return [(start, end, text[start:end])]

    spans = []
    for token_start in range(0, len(tokens), stride):
        window = tokens[token_start : token_start + window_size]
        if not window:
            break
        start = window[0].start()
        end = window[-1].end()
        spans.append((start, end, text[start:end]))
        if token_start + window_size >= len(tokens):
            break
    return spans


def preprocess_row(row: pd.Series) -> dict[str, Any]:
    clean_text = minimal_clean(row.get("text", ""))
    output = {field: row.get(field, "") for field in OUTPUT_FIELDS if field not in {
        "clean_text",
        "char_count",
        "token_count",
        "sentence_count",
        "preprocessing_notes",
    }}
    output.update(
        {
            "clean_text": clean_text,
            "char_count": len(clean_text),
            "token_count": token_count(clean_text),
            "sentence_count": sentence_count(clean_text),
            "preprocessing_notes": "control_character_cleanup; whitespace_normalization; casing_and_punctuation_preserved",
        }
    )
    return output


def segment_label_for_document(label_doc: str) -> tuple[str, str, str]:
    if label_doc == "human":
        return "human", "", "document_label_inherited"
    if label_doc == "ai_generated":
        return "ai_generated", "", "document_label_inherited"
    return "unknown", "mixed_document_segment_unverified", "mixed_document_label_only"


def make_segment_row(
    row: pd.Series,
    segment_type: str,
    segment_index: int,
    start_index: int,
    end_index: int,
    segment_text: str,
) -> dict[str, Any]:
    label_doc = str(row.get("label_doc", ""))
    segment_label, tampering_type, annotation_source = segment_label_for_document(label_doc)
    prefix = {"paragraph": "P", "sentence": "S", "sliding_window": "W"}[segment_type]
    segment_id = f"{row['doc_id']}-{prefix}-{segment_index:06d}"
    return {
        "evidence_id": row.get("evidence_id", ""),
        "evidence_doc_id": row.get("evidence_doc_id", ""),
        "doc_id": row.get("doc_id", ""),
        "segment_id": segment_id,
        "segment_type": segment_type,
        "segment_index": segment_index,
        "start_index": start_index,
        "end_index": end_index,
        "segment_text": segment_text,
        "segment_char_count": len(segment_text),
        "segment_token_count": token_count(segment_text),
        "segment_sentence_count": sentence_count(segment_text),
        "domain": row.get("domain", ""),
        "label_doc": label_doc,
        "segment_label": segment_label,
        "tampering_type": tampering_type,
        "annotation_source": annotation_source,
        "hash_sha256": row.get("hash_sha256", ""),
        "file_name": row.get("file_name", ""),
        "source_record_id": row.get("source_record_id", ""),
    }


def generate_segment_rows(
    preprocessed: pd.DataFrame,
    window_size: int,
    window_stride: int,
) -> Iterator[dict[str, Any]]:
    for _, row in preprocessed.iterrows():
        text = minimal_clean(row.get("clean_text", ""))
        segment_plan = [
            ("paragraph", paragraph_spans(text)),
            ("sentence", sentence_spans(text)),
            ("sliding_window", sliding_window_spans(text, window_size, window_stride)),
        ]
        for segment_type, spans in segment_plan:
            for segment_index, (start, end, segment_text) in enumerate(spans, start=1):
                yield make_segment_row(row, segment_type, segment_index, start, end, segment_text)


def annotation_rows(segment_rows: Iterable[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    for row in segment_rows:
        yield {field: row[field] for field in ANNOTATION_FIELDS}


def run_preprocessing(args: argparse.Namespace, project_root: Path) -> None:
    input_path = args.input or project_root / "dataset_processed" / "extracted_text.csv"
    output_path = args.output or project_root / "dataset_processed" / "preprocessed_text.csv"

    extracted = pd.read_csv(input_path)
    rows = (preprocess_row(row) for _, row in extracted.iterrows())
    write_csv(output_path, rows, OUTPUT_FIELDS)
    print(f"Preprocessed text records: {len(extracted)}")
    print(f"Wrote {output_path.relative_to(project_root)}")


def run_segmentation(args: argparse.Namespace, project_root: Path) -> None:
    input_path = args.input or project_root / "dataset_processed" / "preprocessed_text.csv"
    output_path = args.output or project_root / "dataset_processed" / "segments.csv"
    annotations_path = (
        args.annotations_output
        or project_root / "dataset_processed" / "segment_annotations.csv"
    )

    preprocessed = pd.read_csv(input_path)
    rows_for_segments = generate_segment_rows(
        preprocessed,
        window_size=args.window_size,
        window_stride=args.window_stride,
    )
    write_csv(output_path, rows_for_segments, SEGMENT_FIELDS)

    segments = pd.read_csv(output_path, usecols=ANNOTATION_FIELDS, keep_default_na=False)
    write_csv(annotations_path, segments.to_dict("records"), ANNOTATION_FIELDS)

    segment_count = len(segments)
    print(f"Input documents: {len(preprocessed)}")
    print(f"Generated segments: {segment_count}")
    print(f"Wrote {output_path.relative_to(project_root)}")
    print(f"Wrote {annotations_path.relative_to(project_root)}")


def main() -> None:
    args = parse_args()
    project_root = args.project_root.resolve()
    if args.mode == "segment":
        run_segmentation(args, project_root)
    else:
        run_preprocessing(args, project_root)


if __name__ == "__main__":
    main()

