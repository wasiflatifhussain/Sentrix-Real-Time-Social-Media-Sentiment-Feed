import math
from dataclasses import dataclass
from typing import Optional
from objects.objects import EventMeta, ModelOutput, EventFusionResult

def clamp(x: float, low: float, high: float) -> float:
    return max(low, min(high, x))

# -----------------------------
# Multi-model event fusion
# -----------------------------


# Model reliability priors (can be overridden per call)
MODEL_PRIOR = {
    "finbert": 0.6,
    "fingpt": 0.7,
    "lora": 0.75,
    "mistral": 0.65,
    "llama3": 0.7,
    "other": 0.5,
}

# Risk-aversion profiles for event fusion
EVENT_RISK_PROFILES = {
    "conservative": {
        "agreement_boost": 0.20,
        "disagreement_penalty": 0.25,
        "conf_power": 1.5,
        "engagement_power": 0.5,
        "cred_power": 1.3,
        "w_min": 0.2,
        "w_max": 5.0,
        "w_max_log": 10.0,
        "cred_min": 0.5,
        "cred_max": 1.5,
        "prior_default": 0.5,
        "neutral_threshold": 0.08,
        "conf_eps": 0.05,
    },
    "moderate": {
        "agreement_boost": 0.15,
        "disagreement_penalty": 0.20,
        "conf_power": 1.2,
        "engagement_power": 0.8,
        "cred_power": 1.1,
        "w_min": 0.2,
        "w_max": 5.0,
        "w_max_log": 10.0,
        "cred_min": 0.3,
        "cred_max": 1.6,
        "prior_default": 0.5,
        "neutral_threshold": 0.05,
        "conf_eps": 0.05,
    },
    "aggressive": {
        "agreement_boost": 0.10,
        "disagreement_penalty": 0.10,
        "conf_power": 1.0,
        "engagement_power": 1.0,
        "cred_power": 1.0,
        "w_min": 0.2,
        "w_max": 5.0,
        "w_max_log": 10.0,
        "cred_min": 0.2,
        "cred_max": 1.8,
        "prior_default": 0.5,
        "neutral_threshold": 0.03,
        "conf_eps": 0.05,
    },
}

def label_from_score(score: float, neutral_threshold: float = 0.05) -> str:
    if abs(score) <= neutral_threshold:
        return "neutral"
    return "positive" if score > 0 else "negative"

def engagement_weight_from_counts(likes: int, comments: int, replies: int, w_max_log: float = 10.0) -> float:
    """
    w_engagement = 1 + log(1 + likes + comments + replies)
    """
    raw = 1.0 + math.log1p(max(0, likes) + max(0, comments) + max(0, replies))
    return clamp(raw, 1.0, w_max_log)

def finbert_rows_to_probs(rows: list[dict]) -> dict:
    """
    FinBERT returns a list like: [{"label": "positive", "score": p_pos}, ...]
    """
    probs = {"positive": 0.0, "negative": 0.0, "neutral": 0.0}
    for row in rows or []:
        label = str(row.get("label", "")).lower().strip()
        score = float(row.get("score", 0.0))
        if label in ("positive", "pos"):
            probs["positive"] = score
        elif label in ("negative", "neg"):
            probs["negative"] = score
        elif label in ("neutral", "neu"):
            probs["neutral"] = score
    return probs

def model_output_from_probs(model_id: str, probs: dict) -> ModelOutput:
    """
    score = P(pos) - P(neg)
    label = argmax(P(pos), P(neu), P(neg))
    confidence = maxProb - secondMaxProb (margin)
    """
    p_pos = float(probs.get("positive", 0.0))
    p_neg = float(probs.get("negative", 0.0))
    p_neu = float(probs.get("neutral", 0.0))
    score = clamp(p_pos - p_neg, -1.0, 1.0)
    sorted_probs = sorted([p_pos, p_neu, p_neg], reverse=True)
    conf = clamp(sorted_probs[0] - sorted_probs[1], 0.0, 1.0)
    label = "positive" if p_pos >= p_neu and p_pos >= p_neg else "negative" if p_neg >= p_neu else "neutral"
    return ModelOutput(model_id=model_id, label=label, score=score, confidence=conf)

def fuse_model_outputs(
    outputs: list[ModelOutput],
    meta: Optional[EventMeta] = None,
    profile: str = "moderate",
    model_prior: Optional[dict] = None,
) -> EventFusionResult:
    """
    Weighted fusion with agreement/disagreement logic:
      if labels agree -> confidence boost
      if labels disagree -> penalize via disagreement factor
    """
    meta = meta or EventMeta()
    params = EVENT_RISK_PROFILES.get(profile, EVENT_RISK_PROFILES["moderate"])

    # event-level weight from engagement/credibility/source
    w_engage = engagement_weight_from_counts(meta.likes, meta.comments, meta.reposts, params["w_max_log"])
    w_cred = clamp(meta.cred_score, params["cred_min"], params["cred_max"])
    w_source = max(0.0, float(meta.source_mult))
    w_event = clamp((w_engage ** params["engagement_power"]) * (w_cred ** params["cred_power"]) * w_source,
                    params["w_min"], params["w_max"])

    if not outputs:
        return EventFusionResult(score=0.0, confidence=0.0, weight=w_event, label="neutral")

    # agreement / disagreement factor
    labels = [o.label or label_from_score(o.score, params["neutral_threshold"]) for o in outputs]
    agree = len(set(labels)) == 1
    agree_factor = 1.0 + params["agreement_boost"] if agree else (1.0 - params["disagreement_penalty"])

    priors = dict(MODEL_PRIOR)
    if model_prior:
        priors.update(model_prior)

    weight_sum = 0.0
    score_sum = 0.0
    conf_sum = 0.0
    for o in outputs:
        prior = clamp(float(priors.get(o.model_id, params["prior_default"])), 0.05, 1.0)
        conf = clamp(float(o.confidence), 0.0, 1.0)
        w_model = prior * ((conf + params["conf_eps"]) ** params["conf_power"])
        score_sum += w_model * clamp(o.score, -1.0, 1.0)
        conf_sum += w_model * conf
        weight_sum += w_model

    base_score = 0.0 if weight_sum <= 0 else (score_sum / weight_sum)
    base_conf = 0.0 if weight_sum <= 0 else (conf_sum / weight_sum)

    fused_score = clamp(base_score * agree_factor, -1.0, 1.0)
    fused_conf = clamp(base_conf * agree_factor, 0.0, 1.0)
    fused_label = label_from_score(fused_score, params["neutral_threshold"])

    return EventFusionResult(score=fused_score, confidence=fused_conf, weight=w_event, label=fused_label)

def score_event_multi_model(
    outputs: list[ModelOutput],
    meta: Optional[EventMeta] = None,
    profile: str = "moderate",
    model_prior: Optional[dict] = None,
) -> EventFusionResult:
    return fuse_model_outputs(outputs, meta=meta, profile=profile, model_prior=model_prior)

def score_event_from_finbert_rows(
    rows: list[dict],
    meta: Optional[EventMeta] = None,
    profile: str = "moderate",
    model_id: str = "finbert",
) -> EventFusionResult:
    probs = finbert_rows_to_probs(rows)
    out = model_output_from_probs(model_id, probs)
    return fuse_model_outputs([out], meta=meta, profile=profile)

