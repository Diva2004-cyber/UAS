# Evidence Sources

This document records the raw evidence package prepared for Phase 2 of:

Detection of AI-Generated Text as Digital Evidence Tampering Using Stylometric and Entropy-Based Analysis

## Current Scope

The project now focuses on **document evidence only**. Email and chat datasets
have been removed from the active MVP scope so the implementation stays
realistic for the UAS timeline and remains centered on digital evidence
tampering in document-like text artifacts.

## Current Raw Evidence Inventory

| Folder | Domain | Normalized Label | Current Files | Formats | Notes |
|---|---|---|---:|---|---|
| `evidence_raw/documents/human/` | `document` | `human` | 6 | `.parquet` | Human-authored document evidence. |
| `evidence_raw/documents/ai-generated/` | `document` | `ai_generated` | 7 | `.json`, `.jsonl`, `.parquet` | AI-generated document evidence from manually curated sources. |
| `evidence_raw/documents/mix/` | `document` | `mixed` | 12 | `.csv` | Mixed/tampered document evidence. |

## Label Mapping for Later Phases

During Phase 3 and later processing, use the folder name as the initial label
source:

| Raw Folder Name | `label_doc` |
|---|---|
| `human` | `human` |
| `ai-generated` | `ai_generated` |
| `mix` | `mixed` |

All records should use `domain = document`.

## Intended Use in Later Phases

- Phase 3 will register the document evidence files, assign `evidence_id` and
  `doc_id`, compute SHA-256 hashes, and create working copies.
- Phase 4 will extract or normalize text from `.csv`, `.json`, `.jsonl`, and
  `.parquet` files.
- Phase 5 will preserve or derive segment annotations for mixed/tampered
  documents where the source format supports it.
- Later reports must state that the active experiment scope is document-only,
  while the forensic workflow remains generalizable to other textual evidence
  types in future work.

## Limitations

- Email and chat evidence are currently out of scope for implementation.
- Large files should be sampled in later phases to keep experiments manageable.
- The `mixed` class may contain dataset-specific annotation formats; Phase 4
  must inspect columns before assuming segment boundaries are available.
