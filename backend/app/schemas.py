"""Pydantic models shared by detectors, fusion and the API."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Signal(BaseModel):
    """One measured or matched piece of evidence."""

    id: str
    name: str
    category: Literal["image", "audio", "message", "url", "cross-modal"]
    value: str | float | bool | None = None
    direction: Literal["suspicious", "reassuring", "neutral"]
    weight: float = Field(ge=0.0, le=1.0)
    detail: str


class AnalysisResult(BaseModel):
    """Unified response for every analysis endpoint."""

    modality: Literal["image", "audio", "message", "combined"]
    risk_score: int = Field(ge=0, le=100)
    risk_level: Literal["low", "medium", "high"]
    confidence: Literal["low", "medium", "high"]
    headline: str = ""
    signals: list[Signal] = []
    explanation: str = ""
    next_steps: list[str] = []
    artifacts: dict[str, Any] = {}
    limitations: list[str] = []
    processing_ms: int = 0
    model_versions: dict[str, str] = {}


class MessageRequest(BaseModel):
    """Body for POST /api/analyze/message."""

    text: str
    sender_hint: str | None = None


class ErrorBody(BaseModel):
    """Structured error."""

    code: str
    message: str
