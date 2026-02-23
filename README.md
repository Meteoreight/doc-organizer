# GMP Document Organizer

A support tool to organize GMP documents for user findability and AI readiness.

## Features
- Document list with sortable columns (document number, name, tags)
- Right detail pane with manual edits for metadata and Veeva link
- Add by document number, CSV import/export
- Match search with yellow highlight
- Semantic search against chunked document body
- Auto-download PDF + metadata generation (LLM) + embeddings/vector index creation
- Regenerate action to rerun metadata + embeddings
- Delete documents

## Configuration
Set values in `.env`:
- `base_url`, `api_key`, `llm_model`
- `embedding_base_url`, `embedding_api_key`, `embedding_model`
- `top_k`, `chunk_size`, `chunk_overlap`
- `document_url_header` (uses `document_url_header/document_number.pdf`)
- `llm_provider` (`azure_openai` or `ollama`)
- `embedding_provider` (`azure_openai` or `ollama`)

## Run with Docker Compose
```bash
docker compose up --build
```

Then open: http://localhost:8000

## Local run
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
