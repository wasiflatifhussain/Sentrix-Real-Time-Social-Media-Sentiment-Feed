import json
import logging
import math
import os
import re
from dataclasses import dataclass
from typing import Any, Optional

from huggingface_hub import InferenceClient

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - depends on optional local install state
    OpenAI = None

from sentiment_service.messaging.schemas import CleanedEvent
from sentiment_service.objects.objects import Event

logger = logging.getLogger(__name__)

DEFAULT_OPENROUTER_MODEL = "qwen/qwen-2.5-7b-instruct"
DEFAULT_OPENROUTER_HTTP_REFERER = "http://localhost"
DEFAULT_OPENROUTER_APP_TITLE = "sentiment-service"
DEFAULT_NEUTRAL_PROBS = {
    "positive": 0.0,
    "neutral": 1.0,
    "negative": 0.0,
}
OPENROUTER_SYSTEM_PROMPT = """
You are a financial sentiment classifier.
Classify the text sentiment toward the mentioned stock, company, or market signal.
Return only a JSON object with exactly these numeric keys:
- positive
- neutral
- negative
The values must be probabilities between 0 and 1 and should sum to 1.
""".strip()
JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def normalize_probs(payload: dict[str, Any] | None) -> dict[str, float]:
    probs = dict(DEFAULT_NEUTRAL_PROBS)
    if isinstance(payload, dict):
        for label in probs:
            try:
                probs[label] = _clamp(float(payload.get(label, probs[label])), 0.0, 1.0)
            except (TypeError, ValueError):
                logger.warning("Invalid probability for label=%s payload=%s", label, payload)

    total = sum(probs.values())
    if total <= 0.0:
        return dict(DEFAULT_NEUTRAL_PROBS)
    return {label: value / total for label, value in probs.items()}


def probs_to_rows(probs: dict[str, float]) -> list[dict[str, float]]:
    normalized = normalize_probs(probs)
    return [
        {"label": "positive", "score": normalized["positive"]},
        {"label": "neutral", "score": normalized["neutral"]},
        {"label": "negative", "score": normalized["negative"]},
    ]


def finbert_rows_to_probs(rows: list[dict]) -> dict[str, float]:
    probs = {"positive": 0.0, "negative": 0.0, "neutral": 0.0}
    for row in rows or []:
        label = str(row.get("label", "")).lower().strip()
        try:
            score = float(row.get("score", 0.0))
        except (TypeError, ValueError):
            continue
        if label in ("positive", "pos"):
            probs["positive"] = score
        elif label in ("negative", "neg"):
            probs["negative"] = score
        elif label in ("neutral", "neu"):
            probs["neutral"] = score
    return normalize_probs(probs)


def signed_score_from_probs(probs: dict[str, float]) -> float:
    p_pos = float(probs.get("positive", 0.0))
    p_neg = float(probs.get("negative", 0.0))
    return _clamp(p_pos - p_neg, -1.0, 1.0)


def confidence_from_probs(probs: dict[str, float]) -> float:
    p_pos = float(probs.get("positive", 0.0))
    p_neg = float(probs.get("negative", 0.0))
    p_neu = float(probs.get("neutral", 0.0))
    sorted_probs = sorted([p_pos, p_neu, p_neg], reverse=True)
    margin = sorted_probs[0] - sorted_probs[1]
    return _clamp(margin, 0.0, 1.0)


def calibrate_confidence_margin(
    margin: float,
    temperature: float = 1.5,
    eps: float = 1e-6,
) -> float:
    m = _clamp(float(margin), 0.0, 1.0)
    logit = math.log((m + eps) / (1.0 - m + eps))
    return _clamp(
        1.0 / (1.0 + math.exp(-logit / max(eps, temperature))),
        0.0,
        1.0,
    )


def label_from_probs(probs: dict[str, float]) -> str:
    p_pos = float(probs.get("positive", 0.0))
    p_neg = float(probs.get("negative", 0.0))
    p_neu = float(probs.get("neutral", 0.0))
    if p_pos >= p_neu and p_pos >= p_neg:
        return "positive"
    if p_neg >= p_neu:
        return "negative"
    return "neutral"


def apply_probs_to_event(event: CleanedEvent | Event, probs: dict[str, float]) -> None:
    normalized = normalize_probs(probs)
    event.response = probs_to_rows(normalized)
    event.absolute_score = signed_score_from_probs(normalized)
    event.conf = confidence_from_probs(normalized)
    event.label = label_from_probs(normalized)


class ProbabilitySentimentClient:
    model_id = "other"

    def run_cleaned_event(
        self,
        event: CleanedEvent,
    ) -> None:
        logger.info(
            "start the operation of %s - getting response regarding %s",
            self.__class__.__name__,
            event.event_id,
        )
        try:
            apply_probs_to_event(event, self.assess_probs(event.text_normalized))
        except Exception:
            logger.exception(
                "Unexpected error during %s for eventId=%s",
                self.__class__.__name__,
                event.event_id,
            )
            apply_probs_to_event(event, DEFAULT_NEUTRAL_PROBS)
        finally:
            logger.info(
                "finished the operation of %s - getting response regarding %s",
                self.__class__.__name__,
                event.event_id,
            )

    def run(self, event: Event) -> None:
        logger.info(
            "start the operation of %s - getting response regarding %s",
            self.__class__.__name__,
            getattr(event, "id", None),
        )
        try:
            apply_probs_to_event(event, self.assess_probs(event.content))
        except Exception:
            logger.exception(
                "Unexpected error during %s for eventId=%s",
                self.__class__.__name__,
                getattr(event, "id", None),
            )
            apply_probs_to_event(event, DEFAULT_NEUTRAL_PROBS)
        finally:
            logger.info(
                "finished the operation of %s - getting response regarding %s",
                self.__class__.__name__,
                getattr(event, "id", None),
            )

    def assess_probs(self, text: str) -> dict[str, float]:
        return finbert_rows_to_probs(self.assess(text))

    def assess(self, text: str) -> list[dict[str, float]]:
        return probs_to_rows(self.assess_probs(text))

    def score_details(self, text: str, temperature: float = 1.5) -> "ModelOutput":
        probs = self.assess_probs(text)
        return model_output_from_probs(
            self.model_id,
            probs,
            temperature=temperature,
        )

    def score(self, text: str, temperature: float = 1.5) -> float:
        return self.score_details(text, temperature=temperature).score

    def score_with_confidence(self, text: str, temperature: float = 1.5) -> dict[str, Any]:
        out = self.score_details(text, temperature=temperature)
        return {
            "model_id": out.model_id,
            "label": out.label,
            "score": out.score,
            "confidence": out.confidence,
        }


class FinbertClient(ProbabilitySentimentClient):
    model_id = "finbert"

    def __init__(self, api_key: str | None):
        self.api_key = api_key
        self.client = (
            InferenceClient(
                provider="auto",
                api_key=api_key,
            )
            if api_key
            else None
        )
        if not api_key:
            logger.warning("FinBERT API key is missing; FinBERT scoring will degrade to neutral")

    def read_results_str(self) -> list[str]:
        with open("./filtering-results-str.txt", "r") as f:
            return f.readlines()

    def assess_probs(self, text: str) -> dict[str, float]:
        if not (text or "").strip():
            return dict(DEFAULT_NEUTRAL_PROBS)
        if self.client is None:
            return {}
        try:
            result = self.client.text_classification(
                text,
                model="ProsusAI/finbert",
            )
            return finbert_rows_to_probs(list(result or []))
        except Exception:
            logger.exception("Error occurred during FinBERT text classification")
            return {}


class OpenRouterQwenClient(ProbabilitySentimentClient):
    model_id = "openrouter_qwen7b"

    def __init__(
        self,
        api_key: str | None,
        *,
        model: str | None = None,
        http_referer: str | None = None,
        app_title: str | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model or os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL)
        self.http_referer = http_referer or os.getenv(
            "OPENROUTER_HTTP_REFERER",
            DEFAULT_OPENROUTER_HTTP_REFERER,
        )
        self.app_title = app_title or os.getenv(
            "OPENROUTER_APP_TITLE",
            DEFAULT_OPENROUTER_APP_TITLE,
        )
        self.client = None
        if not api_key:
            logger.warning(
                "OPENROUTER_API_KEY is missing; OpenRouter Qwen scoring will be skipped"
            )
            return
        if OpenAI is None:
            logger.warning(
                "openai package is not installed; OpenRouter Qwen scoring will be skipped"
            )
            return
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.http_referer:
            headers["HTTP-Referer"] = self.http_referer
        if self.app_title:
            headers["X-Title"] = self.app_title
        return headers

    @staticmethod
    def _extract_message_content(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, dict):
            maybe_text = content.get("text")
            if isinstance(maybe_text, str):
                return maybe_text
            maybe_content = content.get("content")
            if isinstance(maybe_content, str):
                return maybe_content
            try:
                return json.dumps(content)
            except TypeError:
                return str(content)
        if isinstance(content, list):
            texts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    maybe_text = item.get("text")
                    if isinstance(maybe_text, str):
                        texts.append(maybe_text)
                        continue
                maybe_text = getattr(item, "text", None)
                if isinstance(maybe_text, str):
                    texts.append(maybe_text)
            return "".join(texts)
        maybe_text = getattr(content, "text", None)
        if isinstance(maybe_text, str):
            return maybe_text
        maybe_content = getattr(content, "content", None)
        if isinstance(maybe_content, str):
            return maybe_content
        return ""

    @staticmethod
    def _extract_json_object_text(content: str) -> str:
        text = (content or "").strip()
        if not text:
            return ""
        fenced = JSON_BLOCK_RE.search(text)
        if fenced:
            return fenced.group(1).strip()
        if text.startswith("{") and text.endswith("}"):
            return text
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return text[start : end + 1]
        return text

    def chat_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        if self.client is None:
            return {}
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            extra_headers=self._headers(),
        )
        message = response.choices[0].message
        parsed = getattr(message, "parsed", None)
        if isinstance(parsed, dict):
            return parsed

        content = self._extract_message_content(message.content)
        json_text = self._extract_json_object_text(content)
        if not json_text:
            refusal = getattr(message, "refusal", None)
            raise ValueError(
                f"OpenRouter returned empty content for JSON response model={self.model} "
                f"finish_reason={getattr(response.choices[0], 'finish_reason', None)} "
                f"refusal={refusal!r}"
            )

        payload = json.loads(json_text)
        if not isinstance(payload, dict):
            raise ValueError("OpenRouter response payload must be a JSON object")
        return payload

    def assess_probs(self, text: str) -> dict[str, float]:
        if not (text or "").strip():
            return dict(DEFAULT_NEUTRAL_PROBS)
        if self.client is None:
            return {}

        try:
            payload = self.chat_json(
                system_prompt=OPENROUTER_SYSTEM_PROMPT,
                user_prompt=text,
                temperature=0.0,
            )
            return normalize_probs(payload)
        except Exception:
            logger.exception("Error occurred during OpenRouter Qwen text classification")
            return {}


class EnsembleSentimentClient(ProbabilitySentimentClient):
    model_id = "ensemble"

    def __init__(
        self,
        *,
        finbert_api_key: str | None,
        openrouter_api_key: str | None,
        openrouter_model: str | None = None,
        http_referer: str | None = None,
        app_title: str | None = None,
    ) -> None:
        self.finbert = FinbertClient(api_key=finbert_api_key)
        self.openrouter = OpenRouterQwenClient(
            api_key=openrouter_api_key,
            model=openrouter_model,
            http_referer=http_referer,
            app_title=app_title,
        )

    def _component_probabilities(self, text: str) -> list[tuple[str, dict[str, float]]]:
        components: list[tuple[str, dict[str, float]]] = []
        for model_id, client in (
            (self.finbert.model_id, self.finbert),
            (self.openrouter.model_id, self.openrouter),
        ):
            probs = client.assess_probs(text)
            if sum(probs.values()) > 0.0:
                components.append((model_id, probs))
        return components

    def assess_probs(self, text: str) -> dict[str, float]:
        if not (text or "").strip():
            return dict(DEFAULT_NEUTRAL_PROBS)

        components = self._component_probabilities(text)
        if not components:
            return dict(DEFAULT_NEUTRAL_PROBS)

        weighted_sum = {label: 0.0 for label in DEFAULT_NEUTRAL_PROBS}
        weight_sum = 0.0

        for model_id, probs in components:
            conf = calibrate_confidence_margin(confidence_from_probs(probs))
            prior = _clamp(
                float(MODEL_PRIOR.get(model_id, MODEL_PRIOR.get("other", 0.5))),
                0.05,
                1.0,
            )
            weight = prior * ((conf + 0.05) ** 1.0)
            if weight <= 0.0:
                continue
            for label, value in probs.items():
                weighted_sum[label] += weight * value
            weight_sum += weight

        if weight_sum <= 0.0:
            return dict(DEFAULT_NEUTRAL_PROBS)

        fused_probs = {
            label: weighted_sum[label] / weight_sum for label in weighted_sum
        }
        return normalize_probs(fused_probs)

    def component_outputs(
        self,
        text: str,
        temperature: float = 1.5,
    ) -> list["ModelOutput"]:
        outputs: list[ModelOutput] = []
        for model_id, probs in self._component_probabilities(text):
            outputs.append(
                model_output_from_probs(
                    model_id=model_id,
                    probs=probs,
                    temperature=temperature,
                )
            )
        return outputs


class LlamaClient:
    pass


class FinGPT:
    pass


def main() -> None:
    pass


if __name__ == "__main__":
    main()


# -----------------------------
# Multi-model fusion + calibration helpers (append-only)
# -----------------------------


@dataclass
class ModelOutput:
    model_id: str
    label: str
    score: float  # signed sentiment in [-1, +1]
    confidence: float = 0.0  # calibrated confidence in [0, 1]


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
    "openrouter_qwen7b": 0.7,
    "ensemble": 0.7,
    "other": 0.5,
}


def model_output_from_probs(
    model_id: str,
    probs: dict,
    temperature: float = 1.5,
) -> ModelOutput:
    score = signed_score_from_probs(probs)
    margin = confidence_from_probs(probs)
    conf = calibrate_confidence_margin(margin, temperature=temperature)
    return ModelOutput(
        model_id=model_id,
        label=label_from_probs(probs),
        score=score,
        confidence=conf,
    )


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
    if not outputs:
        return FusionResult(score=0.0, confidence=0.0, label="neutral")

    priors = dict(MODEL_PRIOR)
    if model_prior:
        priors.update(model_prior)

    labels = [o.label for o in outputs]
    agree = len(set(labels)) == 1
    agree_factor = (
        1.0 + agreement_boost if agree else (1.0 - disagreement_penalty)
    )

    weight_sum = 0.0
    score_sum = 0.0
    conf_sum = 0.0
    for o in outputs:
        prior = _clamp(
            float(priors.get(o.model_id, priors.get("other", 0.5))),
            0.05,
            1.0,
        )
        conf = _clamp(float(o.confidence), 0.0, 1.0)
        w = prior * ((conf + conf_eps) ** conf_power)
        weight_sum += w
        score_sum += w * _clamp(float(o.score), -1.0, 1.0)
        conf_sum += w * conf

    score = 0.0 if weight_sum <= 0 else score_sum / weight_sum
    conf = 0.0 if weight_sum <= 0 else conf_sum / weight_sum
    score = _clamp(score * agree_factor, -1.0, 1.0)
    conf = _clamp(conf * agree_factor, 0.0, 1.0)
    label = (
        "neutral"
        if abs(score) <= neutral_threshold
        else ("positive" if score > 0 else "negative")
    )
    return FusionResult(score=score, confidence=conf, label=label)
