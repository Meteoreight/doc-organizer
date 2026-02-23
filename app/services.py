import csv
import io
import json
from pathlib import Path
from typing import List, Dict

import chromadb
import httpx
from openai import AzureOpenAI, OpenAI
from pypdf import PdfReader

from .config import settings

DATA_DIR = Path("data")
DOCS_DIR = Path("documents")
DATA_DIR.mkdir(exist_ok=True)
DOCS_DIR.mkdir(exist_ok=True)

chroma_client = chromadb.PersistentClient(path=str(DATA_DIR / "chroma"))
collection = chroma_client.get_or_create_collection("gmp_docs")


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(0, end - chunk_overlap)
    return chunks


def _azure_client(base_url: str, api_key: str):
    return AzureOpenAI(azure_endpoint=base_url, api_key=api_key, api_version="2024-06-01")


def llm_generate_metadata(text: str) -> Dict[str, str]:
    prompt = (
        "Generate JSON with keys: name, tags, summary. "
        "name should be concise title in English. "
        "tags should be comma-separated max 6 tags. "
        "summary should be 2-4 sentences in English."
    )
    sample = text[:10000]

    if settings.llm_provider == "ollama":
        payload = {
            "model": settings.llm_model,
            "prompt": f"{prompt}\n\nDocument:\n{sample}",
            "stream": False,
        }
        r = httpx.post(f"{settings.base_url.rstrip('/')}/api/generate", json=payload, timeout=120)
        r.raise_for_status()
        content = r.json().get("response", "{}")
    else:
        client = _azure_client(settings.base_url, settings.api_key)
        res = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": "You are a GMP document analyst."},
                {"role": "user", "content": f"{prompt}\n\nDocument:\n{sample}"},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        content = res.choices[0].message.content or "{}"

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        parsed = {"name": "", "tags": "", "summary": ""}

    return {
        "name": str(parsed.get("name", "")),
        "tags": str(parsed.get("tags", "")),
        "summary": str(parsed.get("summary", "")),
    }


def embedding_for_texts(texts: List[str]) -> List[List[float]]:
    if settings.embedding_provider == "ollama":
        vectors = []
        for t in texts:
            r = httpx.post(
                f"{settings.embedding_base_url.rstrip('/')}/api/embeddings",
                json={"model": settings.embedding_model, "prompt": t},
                timeout=120,
            )
            r.raise_for_status()
            vectors.append(r.json()["embedding"])
        return vectors

    client = _azure_client(settings.embedding_base_url, settings.embedding_api_key)
    res = client.embeddings.create(model=settings.embedding_model, input=texts)
    return [d.embedding for d in res.data]


def download_document(document_number: str) -> Path:
    url = f"{settings.document_url_header.rstrip('/')}/{document_number}.pdf"
    dest = DOCS_DIR / f"{document_number}.pdf"
    with httpx.stream("GET", url, timeout=120) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)
    return dest


def extract_text_from_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def rebuild_embeddings(document_id: int, document_number: str, text: str):
    old = collection.get(where={"document_id": document_id})
    if old and old.get("ids"):
        collection.delete(ids=old["ids"])

    chunks = chunk_text(text, settings.chunk_size, settings.chunk_overlap)
    if not chunks:
        return

    vectors = embedding_for_texts(chunks)
    ids = [f"{document_number}-{i}" for i in range(len(chunks))]
    metadatas = [{"document_id": document_id, "chunk_index": i} for i in range(len(chunks))]
    collection.add(ids=ids, documents=chunks, embeddings=vectors, metadatas=metadatas)


def semantic_search(query: str, limit: int) -> List[Dict]:
    emb = embedding_for_texts([query])[0]
    res = collection.query(query_embeddings=[emb], n_results=limit, include=["documents", "metadatas", "distances"])
    out = []
    for idx, doc in enumerate(res.get("documents", [[]])[0]):
        md = res["metadatas"][0][idx]
        out.append({
            "document_id": md["document_id"],
            "chunk": doc,
            "score": res["distances"][0][idx],
        })
    return out


def parse_csv_numbers(content: bytes) -> List[str]:
    text = content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    numbers = []
    for row in reader:
        if row and row[0].strip() and row[0].strip().lower() != "document_number":
            numbers.append(row[0].strip())
    return numbers
