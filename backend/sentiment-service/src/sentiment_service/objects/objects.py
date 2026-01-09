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
    metadata: Any  # stepp 1 upto here
    response: Any = None  # step 2: finbert response: [{"label": "positive", "score": 0.012}, {...}, {..}] -> {"positive": <score>, "negative": <score>}
    score: float = 0.0  # step3 onwards -> class method -> calcualte_data() 
    conf: float = 0.0  
    label: str = "neutral"

    def calculate(self,):
        self.arrange_response()
        self.calculate_data()
        return

    def arrange_response(self):
        tmp = dict()
        if self.response is not None:
            for re in self.response:
                # print(re)
                tmp[re["label"]] = re["score"]

        self.response = tmp
        return

    def clamp(
        self,
        x: float,
        low: float,
        high: float,
    ) -> float:
        return max(low, min(high, x))

    def calculate_data(self):
        p_pos = float(self.response.get("positive", 0.0))
        p_neg = float(self.response.get("negative", 0.0))
        p_neu = float(self.response.get("neutral", 0.0))

        self.calculate_score(p_pos, p_neg)
        self.calculate_conf(p_pos, p_neg, p_neu)
        self.set_label(p_pos, p_neg, p_neu)
        return

    def calculate_score(self, p_pos, p_neg,):
        self.score = self.clamp(p_pos - p_neg, -1.0, 1.0)
        return

    def calculate_conf(self, p_pos, p_neg, p_neu):
        sorted_probs = sorted([p_pos, p_neu, p_neg], reverse=True)
        self.conf = self.clamp(sorted_probs[0] - sorted_probs[1], 0.0, 1.0)
        return

    def set_label(self, p_pos, p_neg, p_neu):
        if p_pos >= p_neu and p_pos >= p_neg:
            self.label = "positive"
        elif p_neg >= p_neu and p_neg >= p_pos:
            self.label = "negative"
        return

@dataclass
class HourlyLevelScore:
    _id: str = ""
    count: int = 0
    createdAtUtc: int = 0
    hourStartUtc: int = 0
    hourEndUtc: int = 0
    keywordCounts: dict[str, int] = None # unrealistic
    scoreSum: float = 0.0 # avg score
    sourceBreakdown: dict[str, int] = None
    ticker: str = ""
    metrics: dict = None
    
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

