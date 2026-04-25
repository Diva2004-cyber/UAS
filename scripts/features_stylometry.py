"""Stylometric feature extraction for document and segment records.

The features are intentionally numeric, transparent, and lightweight so they
can support baseline modeling without turning the project into a black-box NLP
pipeline.
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
WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z']*\b")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
PUNCTUATION_RE = re.compile(r"[^\w\s]", re.UNICODE)

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an",
    "and", "any", "are", "as", "at", "be", "because", "been", "before",
    "being", "below", "between", "both", "but", "by", "can", "did", "do",
    "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here",
    "hers", "herself", "him", "himself", "his", "how", "i", "if", "in",
    "into", "is", "it", "its", "itself", "just", "me", "more", "most",
    "my", "myself", "no", "nor", "not", "now", "of", "off", "on",
    "once", "only", "or", "other", "our", "ours", "ourselves", "out",
    "over", "own", "same", "she", "should", "so", "some", "such",
    "than", "that", "the", "their", "theirs", "them", "themselves",
    "then", "there", "these", "they", "this", "those", "through", "to",
    "too", "under", "until", "up", "very", "was", "we", "were", "what",
    "when", "where", "which", "while", "who", "whom", "why", "with",
    "would", "you", "your", "yours", "yourself", "yourselves",
}

FUNCTION_WORDS = {
    "a", "an", "the", "and", "or", "but", "if", "while", "because",
    "although", "as", "of", "to", "in", "on", "for", "from", "by",
    "with", "about", "into", "through", "during", "before", "after",
    "above", "below", "between", "under", "over", "is", "am", "are",
    "was", "were", "be", "been", "being", "do", "does", "did", "have",
    "has", "had", "having", "can", "could", "should", "would", "will",
    "shall", "may", "might", "must", "i", "me", "my", "we", "us",
    "our", "you", "your", "he", "him", "his", "she", "her", "it",
    "its", "they", "them", "their", "this", "that", "these", "those",
    "there", "here", "not", "no", "nor", "so", "than", "then",
}

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
    "alpha_count",
    "digit_count",
    "whitespace_count",
    "token_count",
    "word_token_count",
    "unique_token_count",
    "sentence_count",
    "lexical_diversity",
    "hapax_ratio",
    "avg_token_length",
    "token_length_std",
    "sentence_len_mean",
    "sentence_len_std",
    "sentence_len_min",
    "sentence_len_max",
    "punct_count",
    "punctuation_ratio",
    "comma_ratio",
    "period_ratio",
    "question_ratio",
    "exclamation_ratio",
    "quote_ratio",
    "colon_semicolon_ratio",
    "uppercase_ratio",
    "digit_ratio",
    "stopword_count",
    "stopword_ratio",
    "function_word_count",
    "function_word_ratio",
    "char_trigram_count",
    "unique_char_trigram_count",
    "char_trigram_unique_ratio",
    "char_trigram_top1_ratio",
    "char_trigram_top5_ratio",
    "token_freq_burstiness",
    "sentence_length_burstiness",
]


def parse_args() -> argparse.Namespace:
    default_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Extract stylometric features.")
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
        help="Output document feature CSV. Defaults to dataset_processed/features_stylometry_doc.csv.",
    )
    parser.add_argument(
        "--segment-output",
        type=Path,
        default=None,
        help="Output segment feature CSV. Defaults to dataset_processed/features_stylometry_segment.csv.",
    )
    parser.add_argument("--chunk-size", type=int, default=25_000)
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
        raise RuntimeError("Failed to open PowerShell stdin for feature CSV writing.")
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


def burstiness(values: list[int]) -> float:
    if not values:
        return 0.0
    mean_value = statistics.fmean(values)
    if len(values) == 1:
        std_value = 0.0
    else:
        std_value = statistics.pstdev(values)
    denominator = std_value + mean_value
    return safe_float((std_value - mean_value) / denominator) if denominator else 0.0


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text)


def word_tokens_lower(text: str) -> list[str]:
    return [token.lower() for token in WORD_RE.findall(text)]


def sentence_token_lengths(text: str) -> list[int]:
    sentences = [part.strip() for part in SENTENCE_SPLIT_RE.split(text) if part.strip()]
    if not sentences and text.strip():
        sentences = [text.strip()]
    return [len(tokenize(sentence)) for sentence in sentences if sentence]


def char_trigram_stats(text: str) -> tuple[int, int, float, float, float]:
    normalized = " ".join(text.lower().split())
    if len(normalized) < 3:
        return 0, 0, 0.0, 0.0, 0.0
    trigrams = [normalized[index : index + 3] for index in range(len(normalized) - 2)]
    counts = Counter(trigrams)
    total = len(trigrams)
    top_counts = [count for _, count in counts.most_common(5)]
    return (
        total,
        len(counts),
        ratio(len(counts), total),
        ratio(top_counts[0] if top_counts else 0, total),
        ratio(sum(top_counts), total),
    )


def stylometric_features(text_value: Any) -> dict[str, Any]:
    text = "" if pd.isna(text_value) else str(text_value)
    tokens = tokenize(text)
    words_lower = word_tokens_lower(text)
    token_lengths = [len(token) for token in tokens]
    token_freqs = list(Counter(words_lower).values())
    unique_tokens = set(words_lower)
    hapax_count = sum(1 for count in token_freqs if count == 1)
    sentence_lengths = sentence_token_lengths(text)
    char_count = len(text)
    alpha_count = sum(1 for char in text if char.isalpha())
    digit_count = sum(1 for char in text if char.isdigit())
    whitespace_count = sum(1 for char in text if char.isspace())
    punct_count = len(PUNCTUATION_RE.findall(text))
    stopword_count = sum(1 for token in words_lower if token in STOPWORDS)
    function_word_count = sum(1 for token in words_lower if token in FUNCTION_WORDS)
    trigram_count, unique_trigrams, trigram_unique_ratio, trigram_top1, trigram_top5 = (
        char_trigram_stats(text)
    )

    return {
        "char_count": char_count,
        "alpha_count": alpha_count,
        "digit_count": digit_count,
        "whitespace_count": whitespace_count,
        "token_count": len(tokens),
        "word_token_count": len(words_lower),
        "unique_token_count": len(unique_tokens),
        "sentence_count": len(sentence_lengths),
        "lexical_diversity": ratio(len(unique_tokens), len(words_lower)),
        "hapax_ratio": ratio(hapax_count, len(words_lower)),
        "avg_token_length": safe_float(statistics.fmean(token_lengths)) if token_lengths else 0.0,
        "token_length_std": safe_float(statistics.pstdev(token_lengths)) if len(token_lengths) > 1 else 0.0,
        "sentence_len_mean": safe_float(statistics.fmean(sentence_lengths)) if sentence_lengths else 0.0,
        "sentence_len_std": safe_float(statistics.pstdev(sentence_lengths)) if len(sentence_lengths) > 1 else 0.0,
        "sentence_len_min": min(sentence_lengths) if sentence_lengths else 0,
        "sentence_len_max": max(sentence_lengths) if sentence_lengths else 0,
        "punct_count": punct_count,
        "punctuation_ratio": ratio(punct_count, char_count),
        "comma_ratio": ratio(text.count(","), char_count),
        "period_ratio": ratio(text.count("."), char_count),
        "question_ratio": ratio(text.count("?"), char_count),
        "exclamation_ratio": ratio(text.count("!"), char_count),
        "quote_ratio": ratio(text.count('"') + text.count("'"), char_count),
        "colon_semicolon_ratio": ratio(text.count(":") + text.count(";"), char_count),
        "uppercase_ratio": ratio(sum(1 for char in text if char.isupper()), alpha_count),
        "digit_ratio": ratio(digit_count, char_count),
        "stopword_count": stopword_count,
        "stopword_ratio": ratio(stopword_count, len(words_lower)),
        "function_word_count": function_word_count,
        "function_word_ratio": ratio(function_word_count, len(words_lower)),
        "char_trigram_count": trigram_count,
        "unique_char_trigram_count": unique_trigrams,
        "char_trigram_unique_ratio": trigram_unique_ratio,
        "char_trigram_top1_ratio": trigram_top1,
        "char_trigram_top5_ratio": trigram_top5,
        "token_freq_burstiness": burstiness(token_freqs),
        "sentence_length_burstiness": burstiness(sentence_lengths),
    }


def feature_rows(
    frame: pd.DataFrame,
    id_fields: list[str],
    text_column: str,
) -> Iterator[dict[str, Any]]:
    for record in frame.to_dict("records"):
        row = {field: record.get(field, "") for field in id_fields}
        row.update(stylometric_features(record.get(text_column, "")))
        yield row


def write_feature_file(
    input_path: Path,
    output_path: Path,
    id_fields: list[str],
    text_column: str,
    chunksize: int,
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
            for row in feature_rows(chunk, id_fields, text_column):
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
    doc_output = args.doc_output or project_root / "dataset_processed" / "features_stylometry_doc.csv"
    segment_output = (
        args.segment_output or project_root / "dataset_processed" / "features_stylometry_segment.csv"
    )

    if args.level in {"both", "doc"}:
        doc_rows = write_feature_file(
            doc_input,
            doc_output,
            DOC_ID_FIELDS,
            "clean_text",
            args.chunk_size,
        )
        print(f"Document stylometric feature rows: {doc_rows}")
        print(f"Wrote {doc_output.relative_to(project_root)}")

    if args.level in {"both", "segment"}:
        segment_rows = write_feature_file(
            segment_input,
            segment_output,
            SEGMENT_ID_FIELDS,
            "segment_text",
            args.chunk_size,
        )
        print(f"Segment stylometric feature rows: {segment_rows}")
        print(f"Wrote {segment_output.relative_to(project_root)}")


if __name__ == "__main__":
    main()
