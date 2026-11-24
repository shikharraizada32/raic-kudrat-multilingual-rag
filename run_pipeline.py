import asyncio
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import httpx
import pymupdf4llm
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from pydantic import BaseModel

RAW_DIR = Path("data/raw")
OUT_DIR = Path("data/processed")
RAW_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(parents=True, exist_ok=True)


class ScrapedDoc(BaseModel):
    doc_id: str
    source_url: str
    source_org: str
    title: str
    language: Literal["en", "hi"]
    domain: str
    region: str
    content_type: str
    scraped_at: str
    approval_status: str = "pending_review"
    markdown_content: str


def is_valid_hindi(text: str, min_ratio: float = 0.20) -> bool:
    cleaned = re.sub(r"\s+", "", text)
    if not cleaned:
        return False
    devanagari = len(re.findall(r"[\u0900-\u097F]", cleaned))
    return (devanagari / len(cleaned)) >= min_ratio


def clean_markdown(md: str, region: str) -> str:
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    if region == "global_clinical" and re.search(r"\b(988|911)\b", md):
        md += (
            "\n\n> **India Emergency & Support Note:** In India, call **112** for medical emergencies "
            "or **1800-599-0019** (KIRAN 24/7 Mental Health Helpline, Govt. of India).\n"
        )
    return md


async def fetch_pdf(src: dict) -> ScrapedDoc | None:
    pdf_path = RAW_DIR / f"{src['doc_id']}.pdf"
    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            resp = await client.get(src["url"])
            resp.raise_for_status()
            pdf_path.write_bytes(resp.content)

        md = pymupdf4llm.to_markdown(str(pdf_path))
        md = clean_markdown(md, src["region"])
        status = "pending_review"
        if src["language"] == "hi" and not is_valid_hindi(md):
            status = "needs_ocr"

        return ScrapedDoc(
            **{k: src[k] for k in ["doc_id", "source_org", "title", "language", "domain", "region", "content_type"]},
            source_url=src["url"],
            scraped_at=datetime.now(timezone.utc).isoformat(),
            approval_status=status,
            markdown_content=md,
        )
    except Exception as e:
        print(f"[ERROR PDF] {src['doc_id']}: {e}")
        return None


async def scrape_all(sources: list[dict]) -> list[dict]:
    existing_path = OUT_DIR / "approved_docs.json"
    existing = {}
    if existing_path.exists():
        for d in json.loads(existing_path.read_text(encoding="utf-8")):
            if len(d["markdown_content"].split()) >= 60 and d["approval_status"] == "pending_review":
                existing[d["doc_id"]] = d

    run_cfg = CrawlerRunConfig(
        excluded_tags=["nav", "footer", "header", "aside", "script", "style"],
        remove_overlay_elements=True,
        word_count_threshold=15,
    )

    results: list[dict] = []
    async with AsyncWebCrawler() as crawler:
        for src in sources:
            if src["doc_id"] in existing:
                print(f"Skipping [{src['doc_id']}] (already cached OK)")
                results.append(existing[src["doc_id"]])
                continue

            print(f"Fetching [{src['doc_id']}]...")
            if src["content_type"] == "pdf":
                doc = await fetch_pdf(src)
                if doc:
                    results.append(doc.model_dump())
                continue

            res = await crawler.arun(url=src["url"], config=run_cfg)
            if not res.success:
                print(f"[FAILED HTML] {src['doc_id']}: {res.error_message}")
                continue

            (RAW_DIR / f"{src['doc_id']}.html").write_text(res.html or "", encoding="utf-8")
            md = clean_markdown(res.markdown.raw_markdown or "", src["region"])
            status = "pending_review"
            if src["language"] == "hi" and not is_valid_hindi(md):
                status = "needs_manual_check"

            doc = ScrapedDoc(
                **{k: src[k] for k in ["doc_id", "source_org", "title", "language", "domain", "region", "content_type"]},
                source_url=src["url"],
                scraped_at=datetime.now(timezone.utc).isoformat(),
                approval_status=status,
                markdown_content=md,
            )
            results.append(doc.model_dump())
            await asyncio.sleep(1.5)

    return results


def chunk_documents(docs: list[dict]) -> list[dict]:
    md_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
        strip_headers=False,
    )
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=150)

    all_chunks = []
    for doc in docs:
        if len(doc["markdown_content"].split()) < 40:
            continue
        sections = md_splitter.split_text(doc["markdown_content"])
        idx = 0
        for sec in sections:
            for piece in text_splitter.split_text(sec.page_content):
                all_chunks.append({
                    "chunk_id": f"{doc['doc_id']}_c{idx:03d}",
                    "doc_id": doc["doc_id"],
                    "text": piece,
                    "metadata": {
                        "source_url": doc["source_url"],
                        "source_org": doc["source_org"],
                        "title": doc["title"],
                        "language": doc["language"],
                        "domain": doc["domain"],
                        "region": doc["region"],
                        "headings": sec.metadata,
                    },
                })
                idx += 1
    return all_chunks


def export_review_manifest(docs: list[dict], csv_path: Path):
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["doc_id", "title", "source_org", "language", "domain", "word_count", "approval_status", "source_url"])
        for d in docs:
            words = len(d["markdown_content"].split())
            writer.writerow([d["doc_id"], d["title"], d["source_org"], d["language"], d["domain"], words, d["approval_status"], d["source_url"]])


async def main():
    sources = json.loads(Path("seed_sources.json").read_text(encoding="utf-8"))
    docs = await scrape_all(sources)
    chunks = chunk_documents(docs)

    (OUT_DIR / "approved_docs.json").write_text(json.dumps(docs, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "rag_chunks.json").write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    export_review_manifest(docs, OUT_DIR / "source_review_manifest.csv")

    print(f"\nDone! Total docs: {len(docs)} -> Total chunks: {len(chunks)}")


if __name__ == "__main__":
    asyncio.run(main())
