"""Pydantic v2 schemas for the Legal Rights Assistant pipeline."""
from pydantic import BaseModel
from typing import Literal


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    text: str


class Source(BaseModel):
    id: str
    heading: str
    act: str
    section: str
    source_file: str
    text: str = ""
    formerly_ipc: str = ""


class Forum(BaseModel):
    name: str
    why: str
    time_limit: str | None = None
    kb_ref: str
    category: Literal["safety", "institutional", "criminal", "legal_aid", "national", "other"] = "other"


class RoadmapAction(BaseModel):
    text: str
    basis: Literal["kb", "general_guidance"]
    kb_ref: str | None = None
    time_limit: str | None = None


class RoadmapStep(BaseModel):
    step: int
    kind: Literal["immediate", "institutional", "legal"]
    title: str
    actions: list[RoadmapAction]


class AskResult(BaseModel):
    off_topic: bool
    answer: str
    verified: bool
    fallback: bool
    sources: list[Source]
    disclaimer: str
    resolved_query: str
    cited_source_ids: list[str] = []
    routing: list[Forum] = []
    needs_info: list[str] = []
    roadmap: list[RoadmapStep] = []


class DraftRequest(BaseModel):
    narrative: str
    recipient: Literal["SHO", "ICC", "LCC", "Protection Officer"] | None = None
    details: dict[str, str] = {}


class DraftField(BaseModel):
    key: str
    label: str
    value: str
    is_placeholder: bool
    source: Literal["user_form", "user_text", "placeholder"]


class DraftResult(BaseModel):
    recipient: str
    recipient_title: str
    subject: str
    fields: list[DraftField]
    body: str
    missing_fields: list[str]
    notes: list[str]
    references: list[str] = []  # possibly relevant sections, retrieved from the knowledge base
    disclaimer: str

