# Kudrat Foundation — Multilingual SCI Knowledge Companion (Data Ingestion & RAG Chunking Pipeline)

**Responsible AI Consortium (RAIC) — Team 03 | Partner: Kudrat Foundation, India**[cite: 1, 2]

This repository contains the **Document Preparation, Data Cleaning, and Structure-Based Chunking Pipeline** for the **AI Knowledge Companion for People with Spinal Cord Injury (SCI)**[cite: 2, 3]. It transforms curated, authoritative Indian and international SCI resources (in English and Hindi) into validated, metadata-rich Markdown chunks ready for multilingual embedding and Retrieval-Augmented Generation (RAG)[cite: 2, 3].

---

## 1. Architecture Alignment

This pipeline implements the **Document Preparation** stage of our multilingual RAG architecture[cite: 3]:

```text
Curated Web & PDF Sources (EN / HI)
        │
        ▼
Async Scraper (Crawl4AI) & PDF Extractor (PyMuPDF4LLM)
        │
        ▼
Devanagari Unicode Validation + Boilerplate & Helpline Sanitization
        │
        ▼
Structure-Based Markdown Chunking (H1 / H2 / H3 Hierarchy Preserved)
        │
        ▼
[source_review_manifest.csv]  ──► Human-in-the-Loop Approval Gate
[approved_docs.json]          ──► Cleaned Full-Document Store
[rag_chunks.json]             ──► Shared Multilingual Vector Store (Top-30 Cosine → Top-5 Rerank)
```

---

## 2. Knowledge Base Coverage (5 Core Domains)

All sources in `seed_sources.json` are mapped to the five support pillars defined in the Kudrat Foundation project brief[cite: 2]:

1. **Government Schemes & Legal Rights (`government_schemes`):**
   * Department of Empowerment of Persons with Disabilities (DEPwD) — ADIP Scheme overview & official revised guidelines PDF[cite: 2].
   * ARJUN Portal (DEPwD) — ADIP, RVY, and UDID FAQs and Hindi portal guides (`hi`)[cite: 2].
   * Swavlamban Card Portal — Step-by-step UDID card & disability certificate process[cite: 2].
   * RPwD Act 2016 & Accessibility Guidelines index, `myScheme.gov.in`, and DEPwD Hindi portal (`hi`)[cite: 2].
2. **Assistive Solutions & Financial Support (`assistive_solutions`):**
   * ALIMCO assistive devices & mobility aids catalog[cite: 2].
   * National Divyangjan Finance and Development Corporation (NDFDC) concessional loans & skilling[cite: 2].
   * Kudrat Foundation / TrulyAbled initiative[cite: 2].
3. **India-Specific Rehabilitation (`rehabilitation`):**
   * DEPwD Financial Assistance to Spinal Injuries Centers (ASIC Scheme)[cite: 2].
   * Indian Spinal Injuries Centre (ISIC) physiotherapy & multidisciplinary rehabilitation[cite: 2].
   * The Spinal Foundation India (life after SCI, 24/7 helpline, Indian rehab directory)[cite: 2].
   * Nina Foundation & Soulfree (INSPIRE integrated spinal rehabilitation)[cite: 2].
4. **Healthcare & Clinical Management (`healthcare`):**
   * World Health Organization (WHO) Spinal Cord Injury Fact Sheet[cite: 2].
   * MSKTC Complete SCI Factsheet Collection (Autonomic Dysreflexia, Neurogenic Bladder/Bowel, Pressure Injuries, Spasticity, Depression & Adjustment)[cite: 2].
5. **Everyday Living & Livelihood (`daily_living`):**
   * Safe wheelchair transfer techniques and post-injury daily management[cite: 2].
   * EnAble India livelihood, skilling, and employment services for Persons with Disabilities[cite: 2].

---

## 3. Key Engineering & Responsible AI Features

* **Structure-Preserving Extraction:** Instead of flat text scraping (which destroys eligibility tables and section context), `Crawl4AI` and `PyMuPDF4LLM` convert HTML pages and multi-page official PDFs into clean Markdown (`#`, `##`, `###`, lists, and tables)[cite: 3].
* **Heading-Aware Chunking:** Uses `MarkdownHeaderTextSplitter` (`h1`, `h2`, `h3`) followed by `RecursiveCharacterTextSplitter` (`chunk_size=1200`, `chunk_overlap=150`) so every chunk retains its exact section hierarchy (`headings`) and `source_url` for verifiable citations[cite: 3].
* **Hindi Devanagari Encoding Check (`is_valid_hindi`):** Validates that Hindi documents contain genuine Unicode Devanagari characters (`\u0900–\u097F`) rather than garbled legacy non-Unicode fonts (such as *Kruti Dev* or *Chanakya*) common on older Indian government websites, automatically flagging anomalies for OCR[cite: 3].
* **Regional & Clinical Context Separation:** Every document is tagged with `region` (`india_national` vs. `global_clinical`) so India-specific schemes and global clinical guidance remain cleanly distinguishable during retrieval and prompt grounding[cite: 3].
* **India Helpline Safety Guardrail:** Global clinical documents mentioning US emergency numbers (`911` / `988`) are automatically appended with verified Indian emergency and support numbers (`112` Emergency, `1800-599-0019` KIRAN 24/7 Mental Health Helpline)[cite: 2].
* **Human-in-the-Loop Governance:** Exports `source_review_manifest.csv` with word counts, language tags, and `approval_status` (`pending_review` / `approved`) for domain expert sign-off prior to vector ingestion[cite: 3, 5].

---

## 4. Repository Structure

```text
kudrat-rag-scraper/
├── run_pipeline.py                     # End-to-end async scraper, PDF extractor, cleaner & chunker
├── seed_sources.json                   # Curated registry of verified URLs, domains, languages & regions
├── requirements.txt                    # Python dependencies
├── README.md                           # Project documentation
└── data/
    └── processed/
        ├── source_review_manifest.csv  # Human-readable audit table for team & partner approval
        ├── approved_docs.json          # Full cleaned Markdown documents with source metadata
        └── rag_chunks.json             # 800+ heading-split chunks ready for embedding
```

*(Note: `venv/` and `data/raw/` HTML/PDF caches are excluded via `.gitignore` to keep the repository lightweight.)*

---

## 5. How to Reproduce Locally

### Prerequisites
* Python **3.10+** (tested on Python 3.12 on macOS)

### Setup & Run
```bash
# 1. Create and activate virtual environment
python3.12 -m venv venv
source venv/bin/activate

# 2. Install dependencies and Playwright browser binary
pip install -r requirements.txt
crawl4ai-setup

# 3. Run the ingestion & chunking pipeline
python run_pipeline.py
```

---

## 6. Output Data Schema (`rag_chunks.json`)

Each entry in `data/processed/rag_chunks.json` follows this schema[cite: 3, 5]:

```json
{
  "chunk_id": "depwd_adip_guidelines_pdf_en_c004",
  "doc_id": "depwd_adip_guidelines_pdf_en",
  "text": "### Quantum of Assistance\nFor persons with monthly income up to Rs. 22,500/-...",
  "metadata": {
    "source_url": "[https://adip.depwd.gov.in/files/ADIP_English.pdf](https://adip.depwd.gov.in/files/ADIP_English.pdf)",
    "source_org": "DEPwD India",
    "title": "Revised ADIP Scheme Official Guidelines",
    "language": "en",
    "domain": "government_schemes",
    "region": "india_national",
    "headings": {
      "h2": "Eligibility Criteria",
      "h3": "Quantum of Assistance"
    }
  }
}
```

---

## 7. Next Roadmap Steps

1. **Embedding & Vector Indexing:** Embed `rag_chunks.json` into a shared multilingual vector store (`gemini-embedding-2` vs. `Qwen3-Embedding-8B`)[cite: 3].
2. **Two-Stage Multilingual Retrieval:** Retrieve top-30 candidates via cosine similarity and rerank to top-5 passages using a multilingual cross-encoder (`BAAI/bge-reranker-v2-m3`)[cite: 3].
3. **Bilingual Evaluation Benchmark:** Evaluate Recall@5 and citation faithfulness across a 30+ question Hindi/English test suite covering medical emergencies, assistive schemes, and daily living[cite: 2, 3].