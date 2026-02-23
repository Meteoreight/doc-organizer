from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()


class Settings(BaseModel):
    base_url: str = os.getenv("base_url", "")
    api_key: str = os.getenv("api_key", "")
    llm_model: str = os.getenv("llm_model", "")
    embedding_base_url: str = os.getenv("embedding_base_url", "")
    embedding_api_key: str = os.getenv("embedding_api_key", "")
    embedding_model: str = os.getenv("embedding_model", "")
    top_k: int = int(os.getenv("top_k", "5"))
    chunk_size: int = int(os.getenv("chunk_size", "1000"))
    chunk_overlap: int = int(os.getenv("chunk_overlap", "100"))
    document_url_header: str = os.getenv("document_url_header", "")
    llm_provider: str = os.getenv("llm_provider", "azure_openai")
    embedding_provider: str = os.getenv("embedding_provider", "azure_openai")


settings = Settings()
