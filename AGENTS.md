Berikut adalah **AGENTS.md** yang sudah disesuaikan khusus untuk project kamu:
**“Detection of AI-Generated Text as Digital Evidence Tampering Using Stylometric and Entropy-Based Analysis”**

Struktur ini dibuat ringkas tapi tetap powerful, karena AGENTS.md idealnya jadi **“README untuk AI agent” yang berisi konteks dan aturan kerja proyek** ([agents.md][1])

---

# 📄 AGENTS.md

## 1. Project Overview

This project is a **digital forensic system** for detecting AI-generated text used as potential digital evidence tampering.

The system analyzes text using:

* Stylometric features (writing style)
* Entropy-based analysis (text randomness)

Goal:

> Classify text as **AI-generated or human-written** and provide explainable forensic insights.

---

## 2. Tech Stack

* Language: Python 3.x
* Environment: Jupyter Notebook / Google Colab

Libraries:

* nltk / spaCy → NLP processing
* pandas → data handling
* numpy → entropy calculation
* scikit-learn → machine learning
* matplotlib → visualization

---

## 3. Core Pipeline

The system follows this pipeline:

1. Input text / dataset
2. Preprocessing
3. Feature extraction

   * Stylometric features
   * Entropy features
4. Feature vector construction
5. Classification (ML model)
6. Output:

   * Label (AI / Human)
   * Confidence score
   * Forensic explanation

---

## 4. Dataset Guidelines

Dataset must include:

### Human Text:

* Articles / essays / blogs
* Natural writing (non-AI)

### AI Text:

* Generated from LLMs (ChatGPT, etc.)

Rules:

* Balanced dataset (AI vs Human)
* Minimum 1000 samples
* Preferred format: CSV

---

## 5. Coding Guidelines

General:

* Use clean, modular Python functions
* Avoid hardcoding values
* Use descriptive variable names

Structure:

* preprocessing.py
* feature_extraction.py
* model.py
* main.py

---

## 6. Feature Engineering Rules

### Stylometric Features:

* Sentence length
* Word count
* Vocabulary richness (TTR)
* Punctuation frequency

### Entropy Features:

* Character-level entropy
* Word-level entropy

Always normalize features before modeling.

---

## 7. Modeling Guidelines

Allowed models:

* Logistic Regression
* Random Forest
* Support Vector Machine

Rules:

* Use train-test split (80/20)
* Evaluate with accuracy, precision, recall
* Avoid overfitting

---

## 8. Output Requirements

System must return:

* Classification result (AI / Human)
* Confidence score
* Explanation:

  * entropy level
  * stylometric indicators

Example output:

```
Result: AI-generated  
Confidence: 87%  
Explanation:
- Low entropy detected  
- High sentence uniformity  
```

---

## 9. Forensic Interpretation Rules

The system MUST:

* Provide explainable results
* Avoid black-box decisions
* Frame output as **supporting evidence**, not absolute truth

---

## 10. Constraints

* No deep learning required
* Must run on standard laptop (no GPU required)
* Focus on interpretability over complexity

---

## 11. Do & Don’t

### Do:

* Keep logic explainable
* Use statistical reasoning
* Validate results

### Don’t:

* Use overly complex models
* Ignore feature importance
* Output results without explanation

---

## 12. Future Extensions

* Add web interface (Streamlit)
* Add hybrid text detection
* Compare multiple LLM outputs
