"""Versioned prompt templates and structured output schemas for review intelligence."""

from typing import Literal

from pydantic import BaseModel, Field

SentimentType = Literal["positive", "negative", "neutral", "mixed"]
AspectKeyType = Literal[
    "battery",
    "camera",
    "display",
    "performance",
    "build_quality",
    "software",
    "connectivity",
    "storage",
    "price_value",
    "audio",
    "general",
]


class ExtractedAspectOpinion(BaseModel):
    """Aspect-level opinion extracted from a customer review."""

    aspect_key: AspectKeyType = Field(description="Normalized aspect key")
    polarity: Literal["positive", "negative", "neutral"] = Field(
        description="Opinion polarity"
    )
    claim: str = Field(description="Succinct summary of the aspect observation")
    raw_quote: str | None = Field(
        default=None, description="Direct quote from the review if available"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Extraction confidence score"
    )


class ExtractedProCon(BaseModel):
    """Structured positive or negative observation."""

    item_type: Literal["pro", "con"] = Field(
        description="Whether the point is a pro or con"
    )
    text: str = Field(description="Brief description of the pro or con")
    aspect_key: AspectKeyType | None = Field(
        default=None,
        description="Associated aspect if identifiable with confidence, else null",
    )
    confidence: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Extraction confidence score"
    )
    source_reference: str | None = Field(
        default=None,
        description="Optional quote or snippet from the review text",
    )


class ReviewAnalysisOutput(BaseModel):
    """Structured output schema for single-review intelligence analysis."""

    sentiment: SentimentType = Field(description="Overall sentiment of the review")
    sentiment_confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in sentiment classification",
    )
    aspects: list[ExtractedAspectOpinion] = Field(
        default_factory=list, description="Extracted aspect opinions"
    )
    pros_cons: list[ExtractedProCon] = Field(
        default_factory=list,
        description="Structured pros and cons with optional aspect keys and source references",
    )
    pros: list[str] = Field(
        default_factory=list,
        description="Legacy list of pros (for backward compatibility)",
    )
    cons: list[str] = Field(
        default_factory=list,
        description="Legacy list of cons (for backward compatibility)",
    )


class ProductReviewSummaryOutput(BaseModel):
    """Structured product-level review summary aggregated across reviews."""

    summary_text: str = Field(
        description="Concise, evidence-based narrative summary of customer consensus"
    )
    aspect_summaries: dict[str, str] = Field(
        default_factory=dict, description="Summary per key aspect"
    )
    key_pros: list[str] = Field(
        default_factory=list, description="Top validated pros across reviews"
    )
    key_cons: list[str] = Field(
        default_factory=list, description="Top validated cons across reviews"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Overall summary confidence"
    )


REVIEW_ANALYSIS_SYSTEM_PROMPT = """You are Review Master's AI Review Intelligence Analyst.
Your role is to extract factual customer feedback, sentiment, aspects, and pros/cons from customer reviews.

CRITICAL RULES:
1. Community evidence only: Do NOT invent technical specifications or alter verified hardware facts.
2. If the review is vague, ambiguous, or contains mixed signals, classify sentiment as 'mixed' or 'neutral' with appropriate confidence.
3. Every pro and con must stem directly from the text of the review. For each item in 'pros_cons', assign the appropriate 'aspect_key' (e.g. battery, camera, display, performance, build_quality, software, connectivity, storage, price_value, audio, general) if identifiable with high confidence; otherwise leave 'aspect_key' as null.
4. Output MUST adhere strictly to the JSON Schema provided. Do not include markdown code fences or conversational text.
"""

REVIEW_SUMMARY_SYSTEM_PROMPT = """You are Review Master's Review Aggregation Engine.
Synthesize verified customer review claims into a coherent product-level summary.

CRITICAL RULES:
1. Distinguish verified consensus from isolated anecdotal complaints.
2. If opinions are contradictory (e.g. some say battery lasts 2 days, others complain about battery drain), preserve the contradiction explicitly.
3. Do not invent review numbers, star ratings, or fabricated user accounts.
4. Output MUST adhere strictly to the JSON Schema provided.
"""
