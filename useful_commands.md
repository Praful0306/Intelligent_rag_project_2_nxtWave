# 🚀 Enterprise Data Ingestion & Setup Guide

This guide contains the step-by-step setup, environment preparation, troubleshooting resolutions, and exact commands for running data ingestion reliably into Qdrant.

---

## 🛠️ Phase 1: Environment & Dependency Setup (Run Once)

To avoid missing package errors (`ModuleNotFoundError`, `No module named pip`, etc.), run these steps in your project root (`e:\rag system`):

### 1. Activate the Virtual Environment
#### PowerShell:
```powershell
.\.venv\Scripts\Activate.ps1
```
#### CMD:
```cmd
.\.venv\Scripts\activate.bat
```

---

### 2. Ensure `pip` is Installed in `.venv`
If `pip` is missing inside `.venv`:
```powershell
.\.venv\Scripts\python.exe -m ensurepip --default-pip
```

---

### 3. Install All Required Ingestion Packages
```powershell
.\.venv\Scripts\python.exe -m pip install langchain-google-genai pymupdf sentence-transformers qdrant-client logfire python-dotenv pydantic
```

---

## 🔑 Phase 2: Configure Environment Variables (`.env`)

Ensure your `.env` file contains all necessary keys:

```env
# Qdrant Vector Database
QDRANT_API_KEY=your_qdrant_api_key_here
QDRANT_CLUSTER_ENDPOINT=https://your-cluster-url.aws.cloud.qdrant.io

# Logfire Monitoring & Observability
LOGFIRE_TOKEN=pylf_v2_us_your_logfire_token_here

# LLM & Embeddings (Optional: Fallback to all-mpnet-base-v2 is automatic)
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here
```

> **Logfire Authentication (CLI)**:
> If you prefer logging in via CLI instead of setting `LOGFIRE_TOKEN`:
> ```powershell
> uv run logfire auth
> ```

---

## 📂 Phase 3: Dataset Details

* **Dataset Path**: `project-2-intelligent-rag/zyro-dynamics-hr-corpus`
* **Contents**: 11 HR Policy Documents (`00_Company_Profile.pdf` ... `10_Travel_and_Expense_Policy.pdf`)
* **Qdrant Collection**: `Intellegent_RAG` (Cosine, 768-dim)
* **Embedding Model**: `all-mpnet-base-v2` (768-dim) or Gemini (`gemini-embedding-2-preview`, 3072-dim)

---

## 🎯 Phase 4: Production Ingestion Commands

### 1. Fresh Full Ingestion (Wipes Qdrant & Ingests HR Corpus)
> **Recommended**: Drops any existing Qdrant collection, initializes the collection with the exact vector dimension, and indexes all 11 PDF files.

```powershell
python -m app.ingestion.processor "project-2-intelligent-rag/zyro-dynamics-hr-corpus" hr_policy --wipe
```

---

### 2. Incremental Ingestion (Append Without Dropping Existing Vectors)
```powershell
python -m app.ingestion.processor "project-2-intelligent-rag/zyro-dynamics-hr-corpus" hr_policy
```

---

### 3. Ingest with Clean Ground-Truth Tag (`true`) for Evaluation
```powershell
python -m app.ingestion.processor "project-2-intelligent-rag/zyro-dynamics-hr-corpus" true --wipe
```

---

### 4. Ingest an Entire Root Directory with Multiple Subfolders
```powershell
python -m app.ingestion.processor DATA --wipe
```

---

## 🔍 Verified Checklist of Fixes Applied

| Issue Encountered | Cause | Applied Fix |
| :--- | :--- | :--- |
| `ModuleNotFoundError: app.services.retrieval.embedding` | Singular vs plural filename | Changed import to `app.services.retrieval.embeddings` |
| `name 'parse_pdf' is not defined` | Missing PDF loader import | Added `from app.ingestion.loaders.pdf import parse_pdf` |
| `'module' object is not callable` | Calling `logfire()` as function | Changed to `logfire.span(...)` in `embeddings.py` |
| `Vector dimension error: expected 768, got 384` | Model / dimension mismatch | Standardized model to `SentenceTransformer("all-mpnet-base-v2")` (768-dim) |
| `LogfireConfigError` | Missing write token | Added write token with telemetry scope in `.env` |
