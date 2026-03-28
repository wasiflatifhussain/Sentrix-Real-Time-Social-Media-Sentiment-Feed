import logging

from huggingface_hub import InferenceClient
from sentiment_service.messaging.schemas import CleanedEvent
from sentiment_service.objects.objects import Event

logger = logging.getLogger(__name__)

class FinbertClient:
    def __init__(
        self,
        api_key,
        output_file_path = "./finbert_result_test.json",
    ):
        self.output_file_path = output_file_path
        self.client = InferenceClient(
            provider="auto",
            api_key=api_key,
        )

    def run_cleaned_event(
        self,
        event: CleanedEvent,
    ) -> None:
        logger.info(
            f"start the operation of {self.__class__.__name__} - "
            f"getting Finbert response regarding {event.event_id}"
        )
        res = list()
        try:
            for response in self.assess(event.text_normalized):
                res.append(
                    dict(
                        label = response['label'],
                        score = response['score']
                    )
                )
            event.response = res
        except Exception as e:
           logger.critical(
               f"Unexpected error - {str(e)}"
           )
        finally:
            logger.info(
                f"finished the operation of {self.__class__.__name__} - getting Finbert response regarding {event.event_id}"
            )

        return
    
    def run(self, event: Event):
        print(
            f"start the operation of {self.__class__.__name__} - getting Finbert response regarding {event.event_id}"
        )
        # texts \th {id}!!!")
        res = list()
        try:
            for response in self.assess(event.content):
                res.append(
                    dict(
                        label = response['label'],
                        score = response['score']
                    )
                )
            event.response = res
        except Exception as e:
            print(
                f"Unexpected error: {str(e)}"
            )
        finally: 
            print(
                f"finished the operation of {self.__class__.__name__} - getting Finbert response regarding {event.id}"
            )

    def read_results_str(self,):
        with open("./filtering-results-str.txt", 'r') as f:
            d = f.readlines()
        return d

    def assess(self, text):
        try:
            result = self.client.text_classification(
                text,
                model="ProsusAI/finbert",
            )
            return result
        except Exception as e:
            print(f"Error Occurred: {str(e)}")
            return None

    def write_texts_to_file(self, texts) -> None:
        import json
        with open(self.output_file_path, "w") as f:
            json.dump(texts, f, indent=4)
        return

def main():
    pass
    # fc = FinbertClient()
    # fc.run()


if __name__ == "__main__":
    main()

# -----------------------------
# Multi-model fusion + calibration helpers (append-only)
# -----------------------------

from dataclasses import dataclass
import math
from typing import Optional


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


@dataclass
class ModelOutput:
    model_id: str
    label: str
    score: float            # signed sentiment in [-1, +1]
    confidence: float = 0.0 # calibrated confidence in [0, 1]


@dataclass
class FusionResult:
    score: float
    confidence: float
    label: str


MODEL_PRIOR = {
    "finbert": 0.6,
    "fingpt": 0.7,
    "lora": 0.75,
    "mistral": 0.65,
    "llama3": 0.7,
    "other": 0.5,
}


def finbert_rows_to_probs(rows: list[dict]) -> dict:
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


def signed_score_from_probs(probs: dict) -> float:
    p_pos = float(probs.get("positive", 0.0))
    p_neg = float(probs.get("negative", 0.0))
    return _clamp(p_pos - p_neg, -1.0, 1.0)


def confidence_from_probs(probs: dict) -> float:
    p_pos = float(probs.get("positive", 0.0))
    p_neg = float(probs.get("negative", 0.0))
    p_neu = float(probs.get("neutral", 0.0))
    sorted_probs = sorted([p_pos, p_neu, p_neg], reverse=True)
    margin = sorted_probs[0] - sorted_probs[1]
    return _clamp(margin, 0.0, 1.0)


def calibrate_confidence_margin(margin: float, temperature: float = 1.5, eps: float = 1e-6) -> float:
    """
    Confidence calibration via temperature-scaled logit:
      conf = sigmoid(logit(margin) / T)
      logit(p) = ln(p/(1-p))
    """
    m = _clamp(float(margin), 0.0, 1.0)
    logit = math.log((m + eps) / (1.0 - m + eps))
    return _clamp(1.0 / (1.0 + math.exp(-logit / max(eps, temperature))), 0.0, 1.0)


def label_from_probs(probs: dict) -> str:
    p_pos = float(probs.get("positive", 0.0))
    p_neg = float(probs.get("negative", 0.0))
    p_neu = float(probs.get("neutral", 0.0))
    if p_pos >= p_neu and p_pos >= p_neg:
        return "positive"
    if p_neg >= p_neu:
        return "negative"
    return "neutral"


def model_output_from_probs(model_id: str, probs: dict, temperature: float = 1.5) -> ModelOutput:
    score = signed_score_from_probs(probs)
    margin = confidence_from_probs(probs)
    conf = calibrate_confidence_margin(margin, temperature=temperature)
    return ModelOutput(model_id=model_id, label=label_from_probs(probs), score=score, confidence=conf)


def fuse_model_outputs(
    outputs: list[ModelOutput],
    *,
    model_prior: Optional[dict] = None,
    agreement_boost: float = 0.15,
    disagreement_penalty: float = 0.20,
    conf_power: float = 1.0,
    conf_eps: float = 0.05,
    neutral_threshold: float = 0.05,
) -> FusionResult:
    """
    Weighted fusion:
      w_i = prior_i * (conf_i + eps)^p
      score = Σ w_i s_i / Σ w_i
      agreement -> boost confidence; disagreement -> penalize
    """
    if not outputs:
        return FusionResult(score=0.0, confidence=0.0, label="neutral")

    priors = dict(MODEL_PRIOR)
    if model_prior:
        priors.update(model_prior)

    labels = [o.label for o in outputs]
    agree = len(set(labels)) == 1
    agree_factor = 1.0 + agreement_boost if agree else (1.0 - disagreement_penalty)

    weight_sum = 0.0
    score_sum = 0.0
    conf_sum = 0.0
    for o in outputs:
        prior = _clamp(float(priors.get(o.model_id, priors.get("other", 0.5))), 0.05, 1.0)
        conf = _clamp(float(o.confidence), 0.0, 1.0)
        w = prior * ((conf + conf_eps) ** conf_power)
        weight_sum += w
        score_sum += w * _clamp(float(o.score), -1.0, 1.0)
        conf_sum += w * conf

    score = 0.0 if weight_sum <= 0 else score_sum / weight_sum
    conf = 0.0 if weight_sum <= 0 else conf_sum / weight_sum
    score = _clamp(score * agree_factor, -1.0, 1.0)
    conf = _clamp(conf * agree_factor, 0.0, 1.0)
    label = "neutral" if abs(score) <= neutral_threshold else ("positive" if score > 0 else "negative")
    return FusionResult(score=score, confidence=conf, label=label)


def _score_details(self, text: str, temperature: float = 1.5) -> ModelOutput:
    rows = self.assess(text) or []
    probs = finbert_rows_to_probs(rows)
    return model_output_from_probs("finbert", probs, temperature=temperature)


def _score_signed(self, text: str, temperature: float = 1.5) -> float:
    return _score_details(self, text, temperature=temperature).score


def _score_with_confidence(self, text: str, temperature: float = 1.5) -> dict:
    out = _score_details(self, text, temperature=temperature)
    return {
        "model_id": out.model_id,
        "label": out.label,
        "score": out.score,
        "confidence": out.confidence,
    }


FinbertClient.score = _score_signed
FinbertClient.score_details = _score_details
FinbertClient.score_with_confidence = _score_with_confidence
