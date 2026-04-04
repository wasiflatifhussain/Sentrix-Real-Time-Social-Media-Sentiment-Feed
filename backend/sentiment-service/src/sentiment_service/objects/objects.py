from collections import deque
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
    response: Any = None  # step 2: finbert response: [{"label": "positive", "absolute_score": 0.012}, {...}, {..}] -> {"positive": <absolute_score>, "negative": <absolute_score>}
    absolute_score: float = 0.0  # step3 onwards -> class method -> calcualte_data() 
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
        self.absolute_score = self.clamp(p_pos - p_neg, -1.0, 1.0)
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
    scoreSum: float = 0.0 # avg absolute_score -> this is the thing! that we wnat!
    sourceBreakdown: dict[str, int] = None
    ticker: str = ""
    metrics: dict = None

    # Private fields for weighted average calculation
    _weightedScoreSum: float = 0.0
    _weightSum: float = 0.0
    _avgScore: float = 0.0

    @staticmethod
    def get_metrics_weighting(metrics: dict | None) -> float:
        count: int = 0
        metrics = metrics or {}
        for k in metrics:
            value = metrics.get(k, 0)
            if isinstance(value, (int, float, complex)):
                count += int(value)
            elif isinstance(value, str) and value.isnumeric():
                count += int(value)
        return float(count)

    def add_event(self, event: Event,) -> None:
        # TODO: need to cahnge the logic
        absolute_score: float = event.absolute_score
        weight: float = self.get_count_weighting(event)
        source: str = event.source

        # Update Count
        self.count += 1
        
        # Update Score
        self._weightedScoreSum += (absolute_score * weight)
        self._weightSum += weight
        
        if self._weightSum > 0:
            self._avgScore = self._weightedScoreSum / self._weightSum
            self.scoreSum = self._avgScore  # Update public scoreSum for backward compatibility
        
        # Update Source
        if source:
            if self.sourceBreakdown is None:
                self.sourceBreakdown = {}
            if self.sourceBreakdown.get(source) is None:
                self.sourceBreakdown[source] = 1
            else:
                self.sourceBreakdown[source] += 1

        return

    def get_count_weighting(self, event: Event):
        count: int = 0
        like: int = 0
        reply: int = 0
        comment: int = 0
        for k in event.metrics:
            if (
                isinstance(event.metrics.get(k, 0), (int, float, complex)) or
                (isinstance(event.metrics.get(k, ''), str) and event.metrics.get(k, '').isnumeric())
            ):
                count += int(event.metrics.get(k, 0))
                if k.startswith("like"):
                    like += int(event.metrics.get(k, 0))
                elif k.startswith("reply"):
                    reply += int(event.metrics.get(k, 0))
                elif k.startswith("comment"):
                    comment += int(event.metrics.get(k, 0))
                    
        # weighting: float = 1.0 + math.log1p(max(0, like) + max(0, comment) + max(0, reply))
        return count

    def add_scored_cleaned_event(
        self,
        *,
        cleaned_event: Any,
        sentiment_score: float,
        metrics: dict | None = None,
    ) -> dict[str, float]:
        metrics = metrics or {}
        self.metrics = metrics

        weight = self.get_metrics_weighting(metrics)
        source = getattr(cleaned_event, "source", None)

        self.count += 1
        self._weightedScoreSum += float(sentiment_score) * weight
        self._weightSum += weight

        if self._weightSum > 0:
            self._avgScore = self._weightedScoreSum / self._weightSum
            self.scoreSum = self._avgScore

        if source:
            if self.sourceBreakdown is None:
                self.sourceBreakdown = {}
            if self.sourceBreakdown.get(source) is None:
                self.sourceBreakdown[source] = 1
            else:
                self.sourceBreakdown[source] += 1

        return {
            "event_weight": weight,
            "avg_score": float(self._avgScore),
            "hour_reliability": float(self.hour_reliability()),
        }

    def hour_reliability(
        self,
        min_event_cnt: int = 10,
    ) -> float:
        if self.count <= 0:
            return 0.0
        
        return min(1.0, self.count / float(min_event_cnt))


@dataclass
class TickerLevelScore:
    '''
    TODO list
    1. absolute_score calculation logic + Sliding windows for O(1) complexity
    2. initialization
    '''
    _id: str
    ticker: str
    hour_levels: deque[HourlyLevelScore] = field(
        default_factory=lambda: deque(maxlen=168)
    )
    count: int = 0 # count of record
    absolute_score: float = 0.0 # Nt
    reliability: float = 0.0 # Dt
    weighted_score: float = 0.0 # Nt / Dt
    raw_weighted_score: float = 0.0
    normalized_volatility: float = 1.0
    adjusted_weighted_score: float = 0.0
    startTimestamp: int = 0
    endTimestamp: int = 0
    beta: float = 1 - (2 ** (-1 / 24))  # Weighting of the new hourlevel

    def pop_hour_levels(self) -> None | HourlyLevelScore:
        if len(self.hour_levels) == 0:
            return None
        return self.hour_levels.popleft()

    def top_hour_levels(self) -> HourlyLevelScore | None:
        if len(self.hour_levels) == 0:  # if deque is empty
            return None
        return self.hour_levels[0]
    
    def push_hour_levels(self, hour: HourlyLevelScore) -> None:
        if not len(self.hour_levels) == self.hour_levels.maxlen:
            self.hour_levels.append(hour)
        return        

    def update_hour_levels(self, hour: HourlyLevelScore):
        togo: HourlyLevelScore = self.pop_hour_levels() if (len(self.hour_levels) == self.hour_levels.maxlen) else None

        self.push_hour_levels(hour)

        # update the absolute_score
        self._update_score(new = hour)

        # update the count
        self._update_count(togo = togo, new = hour)

        # update the timestamp
        self._update_timestamp(new = hour)
        return

    def _update_absolute_score(
        self,
        score: float,
        reliability: float,
    ) -> None:
        self.absolute_score = (
            ((1 - self.beta) * self.absolute_score) +  # t-1 score
            (self.beta * score * reliability)  # t score
        )
        return
    
    def _update_reliability_score(
        self,
        reliability: float,
    ) -> None:
        self.reliability = (
            ((1 - self.beta) * self.reliability) +  # t-1 reliability
            (self.beta * reliability)  # t reliability
        )
        return
    
    def _update_weighted_score(self) -> None:
        if self.reliability == 0:
            self.weighted_score = 0.0
            return
        self.weighted_score = self.absolute_score / self.reliability
        return

    def _update_score(
        self,
        new: HourlyLevelScore,
    ) -> None:
        new_reliability = new.hour_reliability()
        new_weighted_score = new.scoreSum

        self._update_absolute_score(score = new_weighted_score, reliability = new_reliability,)

        self._update_reliability_score(reliability = new_reliability)

        self._update_weighted_score()

        return

    def apply_normalized_volatility(
        self,
        factor: float,
    ) -> None:
        try:
            resolved_factor = float(factor)
        except (TypeError, ValueError):
            resolved_factor = 1.0

        self.raw_weighted_score = float(self.weighted_score)
        self.normalized_volatility = resolved_factor
        self.adjusted_weighted_score = (
            self.raw_weighted_score * self.normalized_volatility
        )
        return
    
    def _update_count(
        self, 
        new: HourlyLevelScore,
        togo: HourlyLevelScore | None = None,
    ) -> None:
        if togo is not None:
            self.count = self.count - togo.count + new.count
        else:
            self.count = self.count + new.count
        return
    
    def _update_timestamp(
        self,
        new: HourlyLevelScore,
    ) -> None:
        self.startTimestamp = self.top_hour_levels().hourStartUtc
        self.endTimestamp = new.hourEndUtc
        return
