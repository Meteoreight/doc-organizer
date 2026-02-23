from pydantic import BaseModel
from typing import Optional, List


class DocumentBase(BaseModel):
    document_number: str
    name: str = ""
    tags: str = ""
    summary: str = ""
    veeva_link: str = ""


class DocumentUpdate(BaseModel):
    name: Optional[str] = None
    tags: Optional[str] = None
    summary: Optional[str] = None
    veeva_link: Optional[str] = None


class DocumentRead(DocumentBase):
    id: int

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    items: List[DocumentRead]


class SearchRequest(BaseModel):
    query: str


class AddDocumentRequest(BaseModel):
    document_number: str
