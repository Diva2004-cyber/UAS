# Phase 1 Workflow: Project Setup and Repository Structure

## Objective

Phase 1 prepares the repository foundation for a staged digital forensic
research workflow. It creates the project structure, dependency list,
configuration file, and shared data contract without implementing acquisition,
feature extraction, modeling, or reporting logic yet.

## Repository Structure

```text
evidence_raw/
  documents/
    human/
    ai-generated/
    mix/
evidence_acquired/
  copied_files/
dataset_processed/
scripts/
results/
  tables/
  figures/
  suspicious_segments/
models/
configs/
docs/
```

## Evidence Handling Rules

- Store original source files under `evidence_raw/`.
- The current MVP focuses only on document evidence under
  `evidence_raw/documents/`.
- Do not edit master evidence after it is placed in `evidence_raw/`.
- Later phases must copy files into `evidence_acquired/copied_files/` before
  processing.
- Every acquired item must receive an `evidence_id`, SHA-256 hash, metadata row,
  and document label.
- Generated analysis outputs belong in `dataset_processed/`, `results/`, or
  `models/`, not in the raw evidence folders.

## Next Execution Order

1. Dataset/evidence acquisition.
2. Evidence registration, hashing, and metadata logging.
3. Text extraction and minimal preprocessing.
4. Document segmentation.
5. Stylometric and entropy-based feature extraction.
6. Baseline and hybrid modeling.
7. Segment-level suspicion scoring.
8. Explainability and forensic reporting assets.

## Phase Boundary

This phase intentionally does not create analytical scripts. The purpose is to
make the repository reproducible and defensible before evidence enters the
pipeline.
