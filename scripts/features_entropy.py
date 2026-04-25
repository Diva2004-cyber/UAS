"""Entropy and lightweight perplexity feature extraction.

This module computes transparent statistical regularity features for document
and segment records. Perplexity is implemented as unigram self-perplexity
derived from Shannon entropy, not as a heavy language-model score.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import statistics
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Iterator

import pandas as pd


csv.field_size_limit(2_147_483_647)

TOKEN_RE = re.compile(r"\b[\w']+\b", re.UNICODE)

DOC_ID_FIELDS = [
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
]

SEGMENT_ID_FIELDS = [
    "evidence_id",
    "evidence_doc_id",
    "doc_id",
    "segment_id",
    "segment_type",
    "segment_index",
    "start_index",
    "end_index",
    "domain",
    "label_doc",
    "segment_label",
    "tampering_type",
    "annotation_source",
    "hash_sha256",
    "file_name",
    "source_record_id",
]

FEATURE_FIELDS = [
    "char_count",
    "token_count",
    "unique_char_count",
    "unique_token_count",
    "char_shannon_entropy",
    "char_entropy_normalized",
    "char_unigram_perplexity",
    "token_shannon_entropy",
    "token_entropy_normalized",
    "token_unigram_perplexity",
    "char_bigram_entropy",
    "char_bigram_entropy_normalized",
    "token_bigram_entropy",
    "token_bigram_entropy_normalized",
    "local_char_window_count",
    "local_char_entropy_mean",
    "local_char_entropy_std",
    "local_char_entropy_min",
    "local_char_entropy_max",
    "local_char_entropy_range",
    "local_char_entropy_variation",
    "local_token_window_count",
    "local_token_entropy_mean",
    "local_token_entropy_std",
    "local_token_entropy_min",
    "local_token_entropy_max",
    "local_token_entropy_range",
    "local_token_entropy_variation",
    "local_token_perplexity_mean",
    "local_token_perplexity_std",
]


def parse_args() -> argparse.Namespace:
    default_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Extract entropy/perplexity features.")
    parser.add_argument("--project-root", type=Path, default=default_root)
    parser.add_argument(
        "--doc-input",
        type=Path,
        default=None,
        help="Input document CSV. Defaults to dataset_processed/preprocessed_text.csv.",
    )
    parser.add_argument(
        "--segment-input",
        type=Path,
        default=None,
        help="Input segment CSV. Defaults to dataset_processed/segments.csv.",
    )
    parser.add_argument(
        "--doc-output",
        type=Path,
        default=None,
        help="Output document entropy CSV. Defaults to dataset_processed/features_entropy_doc.csv.",
    )
    parser.add_argument(
        "--segment-output",
        type=Path,
        default=None,
        help="Output segment entropy CSV. Defaults to dataset_processed/features_entropy_segment.csv.",
    )
    parser.add_argument("--chunk-size", type=int, default=25_000)
    parser.add_argument("--char-window-size", type=int, default=300)
    parser.add_argument("--char-window-stride", type=int, default=200)
    parser.add_argument("--token-window-size", type=int, default=75)
    parser.add_argument("--token-window-stride", type=int, default=50)
    parser.add_argument(
        "--level",
        choices=["both", "doc", "segment"],
        default="both",
        help="Which feature matrix to generate.",
    )
    return parser.parse_args()


def powershell_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def ensure_directory(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except FileNotFoundError:
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"New-Item -ItemType Directory -Force -Path {powershell_quote(str(path))} | Out-Null",
            ],
            check=True,
        )


def csv_writer_process(path: Path) -> subprocess.Popen[str]:
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
        raise RuntimeError("Failed to open PowerShell stdin for entropy CSV writing.")
    return process


def close_writer(process: subprocess.Popen[str]) -> None:
    if process.stdin:
        process.stdin.close()
    return_code = process.wait()
    if return_code != 0:
        raise subprocess.CalledProcessError(return_code, process.args)


def safe_float(value: float) -> float:
    if math.isnan(value) or math.isinf(value):
        return 0.0
    return round(value, 6)


def ratio(numerator: float, denominator: float) -> float:
    return safe_float(numerator / denominator) if denominator else 0.0


def shannon_entropy_from_counts(counts: Iterable[int]) -> float:
    counts = [count for count in counts if count > 0]
    total = sum(counts)
    if total <= 0:
        return 0.0
    entropy = 0.0
    for count in counts:
        probability = count / total
        entropy -= probability * math.log2(probability)
    return safe_float(entropy)


def normalized_entropy(entropy: float, alphabet_size: int) -> float:
    if alphabet_size <= 1:
        return 0.0
    return ratio(entropy, math.log2(alphabet_size))


def entropy_of_sequence(sequence: list[str] | str) -> tuple[float, int]:
    if not sequence:
        return 0.0, 0
    counts = Counter(sequence)
    entropy = shannon_entropy_from_counts(counts.values())
    return entropy, len(counts)


def ngram_entropy(items: list[str] | str, n: int) -> tuple[float, int]:
    if len(items) < n:
        return 0.0, 0
    ngrams = [tuple(items[index : index + n]) for index in range(len(items) - n + 1)]
    counts = Counter(ngrams)
    entropy = shannon_entropy_from_counts(counts.values())
    return entropy, len(counts)


def unigram_perplexity(entropy: float) -> float:
    # Since entropy is in bits, 2**entropy gives unigram self-perplexity.
    return safe_float(2 ** entropy) if entropy > 0 else 0.0


def token_list(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def character_windows(text: str, window_size: int, stride: int) -> list[str]:
    if not text:
        return []
    window_size = max(1, window_size)
    stride = max(1, stride)
    if len(text) <= window_size:
        return [text]
    windows = []
    for start in range(0, len(text), stride):
        window = text[start : start + window_size]
        if window:
            windows.append(window)
        if start + window_size >= len(text):
            break
    return windows


def token_windows(tokens: list[str], window_size: int, stride: int) -> list[list[str]]:
    if not tokens:
        return []
    window_size = max(1, window_size)
    stride = max(1, stride)
    if len(tokens) <= window_size:
        return [tokens]
    windows = []
    for start in range(0, len(tokens), stride):
        window = tokens[start : start + window_size]
        if window:
            windows.append(window)
        if start + window_size >= len(tokens):
            break
    return windows


def series_stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {
            "mean": 0.0,
            "std": 0.0,
            "min": 0.0,
            "max": 0.0,
            "range": 0.0,
            "variation": 0.0,
        }
    mean_value = statistics.fmean(values)
    std_value = statistics.pstdev(values) if len(values) > 1 else 0.0
    min_value = min(values)
    max_value = max(values)
    return {
        "mean": safe_float(mean_value),
        "std": safe_float(std_value),
        "min": safe_float(min_value),
        "max": safe_float(max_value),
        "range": safe_float(max_value - min_value),
        "variation": ratio(std_value, mean_value),
    }


def entropy_features(
    text_value: Any,
    char_window_size: int,
    char_window_stride: int,
    token_window_size: int,
    token_window_stride: int,
) -> dict[str, Any]:
    text = "" if pd.isna(text_value) else str(text_value)
    tokens = token_list(text)

    char_entropy, unique_chars = entropy_of_sequence(text)
    token_entropy, unique_tokens = entropy_of_sequence(tokens)
    char_bigram_entropy, unique_char_bigrams = ngram_entropy(text, 2)
    token_bigram_entropy, unique_token_bigrams = ngram_entropy(tokens, 2)

    char_window_entropies = [
        entropy_of_sequence(window)[0]
        for window in character_windows(text, char_window_size, char_window_stride)
    ]
    token_window_entropies = [
        entropy_of_sequence(window)[0]
        for window in token_windows(tokens, token_window_size, token_window_stride)
    ]
    token_window_perplexities = [unigram_perplexity(value) for value in token_window_entropies]
    char_local = series_stats(char_window_entropies)
    token_local = series_stats(token_window_entropies)
    token_perplexity_local = series_stats(token_window_perplexities)

    return {
        "char_count": len(text),
        "token_count": len(tokens),
        "unique_char_count": unique_chars,
        "unique_token_count": unique_tokens,
        "char_shannon_entropy": char_entropy,
        "char_entropy_normalized": normalized_entropy(char_entropy, unique_chars),
        "char_unigram_perplexity": unigram_perplexity(char_entropy),
        "token_shannon_entropy": token_entropy,
        "token_entropy_normalized": normalized_entropy(token_entropy, unique_tokens),
        "token_unigram_perplexity": unigram_perplexity(token_entropy),
        "char_bigram_entropy": char_bigram_entropy,
        "char_bigram_entropy_normalized": normalized_entropy(char_bigram_entropy, unique_char_bigrams),
        "token_bigram_entropy": token_bigram_entropy,
        "token_bigram_entropy_normalized": normalized_entropy(token_bigram_entropy, unique_token_bigrams),
        "local_char_window_count": len(char_window_entropies),
        "local_char_entropy_mean": char_local["mean"],
        "local_char_entropy_std": char_local["std"],
        "local_char_entropy_min": char_local["min"],
        "local_char_entropy_max": char_local["max"],
        "local_char_entropy_range": char_local["range"],
        "local_char_entropy_variation": char_local["variation"],
        "local_token_window_count": len(token_window_entropies),
        "local_token_entropy_mean": token_local["mean"],
        "local_token_entropy_std": token_local["std"],
        "local_token_entropy_min": token_local["min"],
        "local_token_entropy_max": token_local["max"],
        "local_token_entropy_range": token_local["range"],
        "local_token_entropy_variation": token_local["variation"],
        "local_token_perplexity_mean": token_perplexity_local["mean"],
        "local_token_perplexity_std": token_perplexity_local["std"],
    }


def feature_rows(
    frame: pd.DataFrame,
    id_fields: list[str],
    text_column: str,
    char_window_size: int,
    char_window_stride: int,
    token_window_size: int,
    token_window_stride: int,
) -> Iterator[dict[str, Any]]:
    for record in frame.to_dict("records"):
        row = {field: record.get(field, "") for field in id_fields}
        row.update(
            entropy_features(
                record.get(text_column, ""),
                char_window_size,
                char_window_stride,
                token_window_size,
                token_window_stride,
            )
        )
        yield row


def write_feature_file(
    input_path: Path,
    output_path: Path,
    id_fields: list[str],
    text_column: str,
    chunksize: int,
    char_window_size: int,
    char_window_stride: int,
    token_window_size: int,
    token_window_stride: int,
) -> int:
    process = csv_writer_process(output_path)
    assert process.stdin is not None
    writer = csv.DictWriter(
        process.stdin,
        fieldnames=id_fields + FEATURE_FIELDS,
        lineterminator="\n",
    )
    writer.writeheader()

    rows_written = 0
    usecols = id_fields + [text_column]
    try:
        for chunk in pd.read_csv(input_path, usecols=usecols, chunksize=chunksize, keep_default_na=False):
            for row in feature_rows(
                chunk,
                id_fields,
                text_column,
                char_window_size,
                char_window_stride,
                token_window_size,
                token_window_stride,
            ):
                writer.writerow(row)
                rows_written += 1
    finally:
        close_writer(process)
    return rows_written


def main() -> None:
    args = parse_args()
    project_root = args.project_root.resolve()
    doc_input = args.doc_input or project_root / "dataset_processed" / "preprocessed_text.csv"
    segment_input = args.segment_input or project_root / "dataset_processed" / "segments.csv"
    doc_output = args.doc_output or project_root / "dataset_processed" / "features_entropy_doc.csv"
    segment_output = (
        args.segment_output or project_root / "dataset_processed" / "features_entropy_segment.csv"
    )

    if args.level in {"both", "doc"}:
        doc_rows = write_feature_file(
            doc_input,
            doc_output,
            DOC_ID_FIELDS,
            "clean_text",
            args.chunk_size,
            args.char_window_size,
            args.char_window_stride,
            args.token_window_size,
            args.token_window_stride,
        )
        print(f"Document entropy feature rows: {doc_rows}")
        print(f"Wrote {doc_output.relative_to(project_root)}")

    if args.level in {"both", "segment"}:
        segment_rows = write_feature_file(
            segment_input,
            segment_output,
            SEGMENT_ID_FIELDS,
            "segment_text",
            args.chunk_size,
            args.char_window_size,
            args.char_window_stride,
            args.token_window_size,
            args.token_window_stride,
        )
        print(f"Segment entropy feature rows: {segment_rows}")
        print(f"Wrote {segment_output.relative_to(project_root)}")


if __name__ == "__main__":
    main()
