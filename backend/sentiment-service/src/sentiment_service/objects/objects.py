from dataclasses import dataclass, field
from typing import Any


@dataclass
class Event:
    id: str
    timestamp: int
    source: str
    ticker: str
    content: str
    metrics: dict
    metadata: Any
    response: Any = None
    score: float = 0  # default value is the neutral

@dataclass
class HourlLevelScore:
    id: int
    attr_freq: int
    _id: str = ""
    ticker: str = ""
    hourStartUtc: int = 0
    hourEndUtc: int = 0
    count: int = 0
    scoreSum: float = 0.0
    keywordCounts: dict[str, int] = field(default_factory=dict)
    sourceBreakdown: dict[str, int] = field(default_factory=dict)
    createdAtUtc: int = 0
    updatedAtUtc: int = 0
    expireAtUtc: int = 0
    
@dataclass
class EventMeta:
    likes: int = 0
    comments: int = 0
    reposts: int = 0
    # placeholder until we get the credibility service:
    cred_score: float = 1.0   # e.g. botOrCredScore
    # optional source reliability multiplier:
    source_mult: float = 1.0  # e.g. verified channel > random

@dataclass
class EventScore:
    s_e: float               # base sentiment in [-1, +1]
    w_e: float               # final event weight
    weighted_sent: float     # s_e * w_e

@dataclass
class ModelOutput:
    model_id: str
    label: str
    score: float            # signed sentiment in [-1, +1]
    confidence: float = 0.0 # [0, 1]

@dataclass
class EventFusionResult:
    score: float       # fused eventScore in [-1, +1]
    confidence: float  # fused eventConfidence in [0, 1]
    weight: float      # event weight (engagement/credibility/source)
    label: str

