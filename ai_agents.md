# AI Agents Specification

## Purpose
Dokumen ini mendefinisikan peran, tanggung jawab, input, output, dan alur koordinasi antar agen AI di dalam proyek **Detection of AI-Generated Text as Digital Evidence Tampering Using Stylometric and Entropy-Based Analysis**. Tujuannya adalah memecah pipeline investigasi menjadi unit kerja modular yang dapat dijalankan secara sistematis dan mudah diaudit.

---

## 1. Design Principles
Setiap agent harus:
- bekerja pada input yang jelas,
- menghasilkan output yang terdokumentasi,
- tidak mengubah master evidence,
- menjaga traceability terhadap evidence ID,
- mendukung explainability dan forensic defensibility.

---

## 2. Agent Architecture Overview
Framework dibagi menjadi delapan agent utama:
1. Evidence Intake Agent
2. Artifact Extraction Agent
3. Preprocessing & Segmentation Agent
4. Stylometric Analysis Agent
5. Entropy Analysis Agent
6. Classification Agent
7. Explainability Agent
8. Report & Investigation Narrative Agent

Agent-agent ini dapat diorkestrasi secara berurutan atau modular sesuai kebutuhan eksperimen.

---

## 3. Agent Definitions

### 3.1 Evidence Intake Agent
**Objective**
Mengelola akuisisi awal, registrasi evidence, hashing, dan metadata logging.

**Inputs**
- file sumber dari `evidence_raw/`
- data source information
- acquisition notes

**Responsibilities**
- memberi `evidence_id`
- menghitung SHA-256
- mencatat metadata dasar
- membuat `hash_manifest.csv`
- membuat `metadata_log.csv`
- memisahkan master evidence dan working copy

**Outputs**
- evidence manifest
- metadata log
- working copies di `evidence_acquired/`

**Constraints**
- tidak boleh mengubah file asli
- semua evidence harus bisa ditelusuri ke sumbernya

---

### 3.2 Artifact Extraction Agent
**Objective**
Mengekstrak artefak teks utama dan artefak pendukung dari evidence.

**Inputs**
- working copy evidence
- file formats: `.txt`, `.csv`, `.json`, `.eml`, `.docx`, `.pdf`

**Responsibilities**
- ekstraksi isi teks
- ekstraksi metadata aplikasi atau header email
- identifikasi browser traces, file history, atau contextual traces bila tersedia
- menyimpan artifact inventory

**Outputs**
- normalized text files
- extracted metadata
- artifact inventory table

**Optional Supporting Tools**
- Autopsy
- The Sleuth Kit
- FTK Imager

---

### 3.3 Preprocessing & Segmentation Agent
**Objective**
Menyiapkan teks agar siap dianalisis tanpa menghilangkan ciri forensik penting.

**Inputs**
- extracted text
- metadata per dokumen

**Responsibilities**
- whitespace normalization
- control character cleanup
- sentence splitting
- tokenization
- paragraph identification
- sentence-based segmentation
- sliding-window segmentation
- sinkronisasi dengan segment annotations

**Outputs**
- clean text
- segmented text units
- segmentation manifest

**Rules**
- preprocessing harus minimalis
- jangan menghapus ciri stylometric yang relevan

---

### 3.4 Stylometric Analysis Agent
**Objective**
Menghasilkan fitur berbasis gaya bahasa untuk setiap dokumen dan segmen.

**Inputs**
- segmented text

**Responsibilities**
- hitung lexical diversity
- sentence-length statistics
- punctuation ratio
- function-word frequency
- stopword ratio
- trigram profile
- burstiness
- susun feature matrix stylometry

**Outputs**
- `features_stylometry.csv`
- stylometric feature summaries

**Notes**
Agent ini fokus pada **writing style evidence**.

---

### 3.5 Entropy Analysis Agent
**Objective**
Menghasilkan fitur statistik untuk menangkap regularitas dan prediktabilitas teks.

**Inputs**
- segmented text
- optional language model / tokenizer

**Responsibilities**
- hitung character entropy
- hitung token entropy
- hitung Shannon entropy
- hitung perplexity
- hitung sliding-window perplexity
- hitung local entropy variation
- susun feature matrix entropy

**Outputs**
- `features_entropy.csv`
- entropy diagnostics

**Notes**
Agent ini fokus pada **statistical regularity evidence**.

---

### 3.6 Classification Agent
**Objective**
Mengklasifikasikan dokumen dan segmen berdasarkan fitur hybrid.

**Inputs**
- stylometric features
- entropy features
- labels / annotations

**Responsibilities**
- merge feature space
- train baseline models
- train hybrid model
- generate document-level predictions
- generate segment-level suspicion scores
- simpan confusion matrix dan metrics

**Recommended Models**
- Random Forest
- Logistic Regression
- Support Vector Machine

**Outputs**
- trained model files
- predictions per doc
- suspicious segment scores
- evaluation metrics

---

### 3.7 Explainability Agent
**Objective**
Menjelaskan alasan sistem menandai suatu dokumen atau segmen sebagai mencurigakan.

**Inputs**
- trained model
- feature matrix
- predictions

**Responsibilities**
- hitung feature importance
- hasilkan SHAP summary plot
- hasilkan local explanation untuk dokumen tertentu
- ringkas faktor utama yang memengaruhi keputusan

**Outputs**
- explainability figures
- explanation summary per case

**Goal**
Membantu investigator menyusun narasi yang dapat dipertanggungjawabkan.

---

### 3.8 Report & Investigation Narrative Agent
**Objective**
Mengubah output teknis menjadi narasi investigatif dan artefak laporan.

**Inputs**
- evidence manifest
- artifact inventory
- model results
- explainability outputs
- supporting forensic traces

**Responsibilities**
- menyusun tabel hasil analisis
- menyusun ringkasan per evidence
- menghubungkan klasifikasi dengan artefak pendukung
- menulis narasi investigatif yang lebih defensible
- menyiapkan bahan untuk technical report dan slide

**Outputs**
- report-ready tables
- figure captions
- case summaries
- final investigation narrative

---

## 4. Agent Orchestration Flow
```text
Evidence Intake Agent
        ↓
Artifact Extraction Agent
        ↓
Preprocessing & Segmentation Agent
        ↓
 ┌──────────────────────────────┐
 ↓                              ↓
Stylometric Analysis Agent   Entropy Analysis Agent
 └──────────────┬───────────────┘
                ↓
       Classification Agent
                ↓
       Explainability Agent
                ↓
Report & Investigation Narrative Agent
```

---

## 5. Shared Data Contracts
Semua agent harus menggunakan field minimal berikut:
- `evidence_id`
- `doc_id`
- `domain`
- `file_type`
- `hash_sha256`
- `label_doc`

Untuk segment-level processing:
- `segment_id`
- `start_index`
- `end_index`
- `segment_label`
- `tampering_type`

---

## 6. Guardrails
Setiap agent harus mematuhi aturan berikut:
1. Tidak mengubah master evidence.
2. Selalu mempertahankan keterlacakan evidence.
3. Tidak membuat klaim di luar bukti yang tersedia.
4. Tidak menganggap hasil model sebagai kepastian absolut.
5. Menyajikan hasil dalam bahasa probabilistik dan investigatif.
6. Mendokumentasikan error, skipped files, dan extraction failures.

---

## 7. Example Agent Tasks
### Evidence Intake Agent
- "Register all files in `evidence_raw/` and create hash manifest."

### Artifact Extraction Agent
- "Extract text, metadata, and email headers from all supported files."

### Preprocessing Agent
- "Tokenize all extracted documents and generate sentence and sliding-window segments."

### Stylometric Agent
- "Generate stylometric features for each document and each segment."

### Entropy Agent
- "Compute entropy and perplexity-based features for each text segment."

### Classification Agent
- "Train Random Forest on hybrid features and evaluate against baselines."

### Explainability Agent
- "Produce SHAP summary plot and local explanation for suspicious documents."

### Report Agent
- "Generate investigation summary table and report narrative for all suspicious evidence."

---

## 8. Recommended Implementation Mapping
| Agent | Recommended Module |
|---|---|
| Evidence Intake Agent | `scripts/acquisition.py` |
| Artifact Extraction Agent | `scripts/text_extraction.py` |
| Preprocessing & Segmentation Agent | `scripts/preprocess.py` |
| Stylometric Analysis Agent | `scripts/features_stylometry.py` |
| Entropy Analysis Agent | `scripts/features_entropy.py` |
| Classification Agent | `scripts/train_classifier.py` |
| Explainability Agent | `scripts/explainability.py` |
| Report Agent | `scripts/reporting.py` |

---

## 9. Success Criteria for Agents
Agent system dianggap berhasil jika:
- semua evidence berhasil diregistrasi,
- semua text-bearing files berhasil diekstrak atau error-nya terdokumentasi,
- feature matrices terbentuk,
- model dapat dilatih dan dievaluasi,
- segment-level suspicious output tersedia,
- explainability artifacts tersedia,
- narasi laporan dapat dihasilkan dengan konsisten.
