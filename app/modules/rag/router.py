"""RAG search endpoint. Returns the user's most relevant document passages."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.modules.auth.schemas import AuthUser
from app.modules.auth.security import get_current_user
from app.modules.rag import service

router = APIRouter(prefix="/rag", tags=["rag"])


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=8, ge=1, le=50)


class PassageOut(BaseModel):
    text: str
    score: float
    doc_id: str
    chunk_index: int


@router.post("/search", response_model=list[PassageOut])
def search(payload: SearchRequest, user: AuthUser = Depends(get_current_user)) -> list[PassageOut]:
    passages = service.retrieve(payload.query, user_id=user.id, top_k=payload.top_k)
    return [
        PassageOut(text=p.text, score=p.score, doc_id=p.doc_id, chunk_index=p.chunk_index)
        for p in passages
    ]
