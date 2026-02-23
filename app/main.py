from pathlib import Path
from typing import List

from fastapi import FastAPI, Depends, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from sqlalchemy.orm import Session
import csv
import io

from .database import Base, engine, SessionLocal
from .models import Document
from .schemas import DocumentRead, DocumentUpdate, AddDocumentRequest, SearchRequest
from .services import (
    download_document,
    extract_text_from_pdf,
    llm_generate_metadata,
    rebuild_embeddings,
    semantic_search,
    parse_csv_numbers,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="GMP Document Organizer")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/documents", response_model=List[DocumentRead])
def list_documents(sort_by: str = "document_number", order: str = "asc", db: Session = Depends(get_db)):
    col = getattr(Document, sort_by, Document.document_number)
    q = db.query(Document).order_by(col.asc() if order == "asc" else col.desc())
    return q.all()


@app.post("/api/documents", response_model=DocumentRead)
def add_document(payload: AddDocumentRequest, db: Session = Depends(get_db)):
    existing = db.query(Document).filter_by(document_number=payload.document_number).first()
    if existing:
        return existing

    doc = Document(document_number=payload.document_number, veeva_link="")
    db.add(doc)
    db.commit()
    db.refresh(doc)

    try:
        path = download_document(doc.document_number)
        text = extract_text_from_pdf(path)
        metadata = llm_generate_metadata(text)
        doc.name = metadata["name"]
        doc.tags = metadata["tags"]
        doc.summary = metadata["summary"]
        doc.local_path = str(path)
        rebuild_embeddings(doc.id, doc.document_number, text)
        db.commit()
        db.refresh(doc)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"document processing failed: {e}")

    return doc


@app.put("/api/documents/{doc_id}", response_model=DocumentRead)
def update_document(doc_id: int, payload: DocumentUpdate, db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(doc, field, value)
    db.commit()
    db.refresh(doc)
    return doc


@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="not found")
    db.delete(doc)
    db.commit()
    return {"ok": True}


@app.post("/api/documents/{doc_id}/regenerate", response_model=DocumentRead)
def regenerate_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="not found")
    if not doc.local_path or not Path(doc.local_path).exists():
        path = download_document(doc.document_number)
        doc.local_path = str(path)

    text = extract_text_from_pdf(Path(doc.local_path))
    metadata = llm_generate_metadata(text)
    doc.name = metadata["name"] or doc.name
    doc.tags = metadata["tags"] or doc.tags
    doc.summary = metadata["summary"] or doc.summary
    rebuild_embeddings(doc.id, doc.document_number, text)
    db.commit()
    db.refresh(doc)
    return doc


@app.post("/api/search/match")
def match_search(payload: SearchRequest, db: Session = Depends(get_db)):
    query = payload.query.strip().lower()
    docs = db.query(Document).all()
    results = []
    for d in docs:
        if query in d.document_number.lower() or query in d.name.lower():
            results.append(DocumentRead.model_validate(d).model_dump())
    return results


@app.post("/api/search/semantic")
def semantic(payload: SearchRequest, db: Session = Depends(get_db)):
    chunks = semantic_search(payload.query, 10)
    by_doc = {}
    for item in chunks:
        doc = db.get(Document, item["document_id"])
        if not doc:
            continue
        if doc.id not in by_doc:
            by_doc[doc.id] = {
                "document": DocumentRead.model_validate(doc).model_dump(),
                "chunks": [],
            }
        by_doc[doc.id]["chunks"].append(item)
    return list(by_doc.values())


@app.post("/api/import")
async def import_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    numbers = parse_csv_numbers(content)
    added = 0
    for n in numbers:
        if not db.query(Document).filter_by(document_number=n).first():
            db.add(Document(document_number=n))
            added += 1
    db.commit()
    return {"added": added}


@app.get("/api/export")
def export_csv(db: Session = Depends(get_db)):
    docs = db.query(Document).order_by(Document.document_number.asc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["document_number", "name", "tags", "summary", "veeva_link"])
    for d in docs:
        writer.writerow([d.document_number, d.name, d.tags, d.summary, d.veeva_link])

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=documents.csv"},
    )
