from sqlalchemy import Column, Integer, String, Text
from .database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    document_number = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, default="")
    tags = Column(String, default="")
    summary = Column(Text, default="")
    veeva_link = Column(String, default="")
    local_path = Column(String, default="")
