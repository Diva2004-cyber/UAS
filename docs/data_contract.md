# Data Contract

This document defines the minimum shared fields used by the investigation
pipeline for the project:

**Detection of AI-Generated Text as Digital Evidence Tampering Using Stylometric and Entropy-Based Analysis**

The current MVP scope uses document datasets only. The goal is to keep every
artifact traceable from evidence intake through analysis, interpretation, and
reporting.

## Document-Level Fields

| Field | Description |
|---|---|
| `evidence_id` | Unique identifier assigned during evidence intake. |
| `doc_id` | Unique document identifier used across processing stages. |
| `file_name` | Original file name of the evidence item. |
| `file_type` | File extension or normalized file format. |
| `domain` | Evidence domain. For the current MVP this should be `document`. |
| `source` | Dataset, simulation source, or acquisition source. |
| `acquisition_date` | Date/time when the evidence was registered. |
| `file_size` | File size in bytes at acquisition time. |
| `hash_sha256` | SHA-256 hash of the acquired evidence file. |
| `label_doc` | Document label: `human`, `ai_generated`, or `mixed`. |
| `notes` | Investigator notes, acquisition context, or limitations. |

## Current Document Folder Mapping

| Raw Folder | Normalized Label | Notes |
|---|---|---|
| `evidence_raw/documents/human/` | `human` | Human-authored document evidence. |
| `evidence_raw/documents/ai-generated/` | `ai_generated` | AI-generated document evidence. |
| `evidence_raw/documents/mix/` | `mixed` | Mixed or tampered document evidence. |

## Segment-Level Fields

| Field | Description |
|---|---|
| `evidence_id` | Evidence identifier inherited from the document record. |
| `evidence_doc_id` | File-level document identifier from Phase 3. |
| `doc_id` | Extracted text record identifier from Phase 4. |
| `segment_id` | Unique segment identifier within the extracted text record. |
| `segment_type` | Segmentation strategy: `paragraph`, `sentence`, or `sliding_window`. |
| `segment_index` | Sequential index for the segment type within the document. |
| `start_index` | Character start index of the segment in the source text. |
| `end_index` | Character end index of the segment in the source text. |
| `segment_text` | Segment text used for analysis. |
| `segment_char_count` | Character count of the segment. |
| `segment_token_count` | Token count of the segment. |
| `segment_sentence_count` | Approximate sentence count of the segment. |
| `label_doc` | Parent document label: `human`, `ai_generated`, or `mixed`. |
| `segment_label` | Segment label: `human`, `ai_generated`, or `unknown` when unavailable. |
| `tampering_type` | Type of manipulation, such as `ai_inserted`, `ai_rewritten`, or blank when not applicable. |
| `annotation_source` | Source of segment label, such as inherited document label or mixed-document placeholder. |

`dataset_processed/segments.csv` stores segment text and counts for analysis.
`dataset_processed/segment_annotations.csv` stores the same segment identifiers
and label fields without `segment_text`, so later evaluation can read
annotations without loading the full segment text file.

## Phase 4 Extraction Output Fields

`dataset_processed/extracted_text.csv` uses these fields:

| Field | Description |
|---|---|
| `evidence_id` | Evidence file identifier from Phase 3. |
| `evidence_doc_id` | File-level `doc_id` from `metadata_log.csv`. |
| `doc_id` | Extracted text record identifier, generated as a child of `evidence_doc_id`. |
| `source_record_id` | Row, line, or item identifier inside the source file. |
| `domain` | Current MVP domain, always `document`. |
| `label_doc` | Normalized label: `human`, `ai_generated`, or `mixed`. |
| `source` | Source folder/dataset note from metadata logging. |
| `file_name` | Source evidence file name. |
| `file_type` | Source evidence file type. |
| `hash_sha256` | SHA-256 hash of the acquired source file. |
| `extraction_method` | Parser strategy used for the source record. |
| `text` | Extracted text before minimal preprocessing. |

`dataset_processed/preprocessed_text.csv` preserves the extraction fields and
adds:

| Field | Description |
|---|---|
| `clean_text` | Minimally cleaned text for analysis. |
| `char_count` | Character count after preprocessing. |
| `token_count` | Regex token count after preprocessing. |
| `sentence_count` | Approximate sentence count after preprocessing. |
| `preprocessing_notes` | Cleanup operations applied to the record. |

## Phase 6 Stylometric Feature Outputs

`dataset_processed/features_stylometry_doc.csv` contains one row per extracted
document record and preserves document identifiers such as `evidence_id`,
`evidence_doc_id`, `doc_id`, `label_doc`, `file_name`, and `hash_sha256`.

`dataset_processed/features_stylometry_segment.csv` contains one row per segment
and preserves segment identifiers such as `segment_id`, `segment_type`,
`start_index`, `end_index`, `segment_label`, `tampering_type`, and
`annotation_source`.

Both matrices include transparent numeric stylometric features:

| Feature Group | Example Fields |
|---|---|
| Lexical diversity | `token_count`, `unique_token_count`, `lexical_diversity`, `hapax_ratio` |
| Sentence statistics | `sentence_len_mean`, `sentence_len_std`, `sentence_len_min`, `sentence_len_max` |
| Punctuation profile | `punctuation_ratio`, `comma_ratio`, `period_ratio`, `question_ratio`, `exclamation_ratio` |
| Function/stopword usage | `stopword_ratio`, `function_word_ratio` |
| Character trigram profile | `char_trigram_unique_ratio`, `char_trigram_top1_ratio`, `char_trigram_top5_ratio` |
| Burstiness | `token_freq_burstiness`, `sentence_length_burstiness` |

## Phase 7 Entropy Feature Outputs

`dataset_processed/features_entropy_doc.csv` contains one row per extracted
document record. `dataset_processed/features_entropy_segment.csv` contains one
row per segment. Both preserve the same identifier fields as the stylometric
matrices, so document-level features can be joined on `doc_id` and segment-level
features can be joined on `segment_id`.

The MVP uses lightweight statistical entropy features, not heavy LLM
perplexity:

| Feature Group | Example Fields |
|---|---|
| Character entropy | `char_shannon_entropy`, `char_entropy_normalized`, `char_unigram_perplexity` |
| Token entropy | `token_shannon_entropy`, `token_entropy_normalized`, `token_unigram_perplexity` |
| N-gram entropy | `char_bigram_entropy`, `token_bigram_entropy` |
| Local variation | `local_char_entropy_variation`, `local_token_entropy_variation` |
| Local window diagnostics | `local_char_window_count`, `local_token_window_count`, `local_token_perplexity_mean` |

`*_unigram_perplexity` is calculated from Shannon entropy as `2 ** entropy`.
It is a transparent regularity proxy and must not be described as a pretrained
language-model perplexity score.

## Guardrails

- Master evidence must not be modified during processing.
- Working copies must remain traceable to `evidence_id` and `hash_sha256`.
- Labels represent research annotations, not absolute legal authorship claims.
- Extraction failures, skipped files, and preprocessing limitations must be documented.
