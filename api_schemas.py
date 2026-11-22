"""API schemas for Legal Rights Assistant FastAPI layer."""
from typing import Literal
from pydantic import BaseModel, Field

from schemas import Turn, AskResult, DraftRequest, DraftField, DraftResult


class AskRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="User's query describing the legal issue or question",
        examples=["Someone shared my private photos without my consent"],
    )
    session_id: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9_-]{8,64}$",
        description="Optional session ID for conversation continuity",
        examples=["c7a9e1b2-3f4a-4b5c-8d9e-0f1a2b3c4d5e"],
    )
    history: list[Turn] | None = Field(
        default=None,
        max_length=20,
        description="Optional previous turns (max 20; used only when no session_id is given)",
    )
    response_lang: Literal["auto", "en", "hi", "hinglish"] = Field(
        default="auto",
        description="Preferred language for the response",
        examples=["auto"],
    )


class AskResponse(AskResult):
    session_id: str = Field(
        ...,
        description="Active session ID for follow-up turns",
        examples=["c7a9e1b2-3f4a-4b5c-8d9e-0f1a2b3c4d5e"],
    )


class HealthResponse(BaseModel):
    status: str = Field(default="ok", examples=["ok"])
    kb_sections: int = Field(..., description="Number of distinct parent knowledge base sections", examples=[135])
    kb_chunks: int = Field(..., description="Number of indexed child knowledge base chunks", examples=[165])
    ollama_reachable: bool = Field(..., description="Whether the local Ollama instance is reachable", examples=[True])
    answer_translation: bool = Field(..., description="Whether answer translation is enabled via ANSWER_TRANSLATION", examples=[False])


class ExampleItem(BaseModel):
    label: str = Field(..., examples=["Harassment at work"])
    query: str = Field(..., examples=["My boss keeps touching me at work"])
    lang: str = Field(..., examples=["en"])


class ExamplesResponse(BaseModel):
    examples: list[ExampleItem]
    disclaimer: str
