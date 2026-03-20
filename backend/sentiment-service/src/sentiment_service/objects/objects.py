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
                tmp[re["label"]] = re["absolute_score"]

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

    def add_event(self, absolute_score: float, weight: float, source: str = None):
        self.count += 1
        
        self._weightedScoreSum += (absolute_score * weight)
        self._weightSum += weight
        
        if self._weightSum > 0:
            self._avgScore = self._weightedScoreSum / self._weightSum
            self.scoreSum = self._avgScore  # Update public scoreSum for backward compatibility
        
        if source:
            if self.sourceBreakdown is None:
                self.sourceBreakdown = {}
            if self.sourceBreakdown.get(source) is None:
                self.sourceBreakdown[source] = 1
            else:
                self.sourceBreakdown[source] += 1

    def hour_reliability(
        self,
        min_event_cnt: int = 10,
    ) -> float:
        if self.count <= 0:
            return 0.0
        
        return min(1.0, self.count / float(min_event_cnt))


class TickerLevelScore:
    '''
    TODO list
    1. absolute_score calculation logic + Sliding windows for O(1) complexity
    2. initialization
    '''
    _id: str
    hour_levels: deque
    ticker: str
    count: int  # count of record
    absolute_score: float  # Nt
    reliability: float  # Dt
    weighted_score: float  # Nt / Dt
    startTimestamp: int
    endTimestamp: int
    beta: float = 1 - (2 ** (-1 / 24))  # Weighting of the new hourlevel

    def __init__(
        self,
        ticker: str,
    ) -> None:
        self.hour_levels: deque[HourlyLevelScore] = deque(maxlen = 168)
        self.ticker = ticker
        self.count = 0
        self.absolute_score = 0.0
        self.weighted_score = 0.0
        self.reliability = 0.0
        return

    def pop_hour_levels(self) -> None | HourlyLevelScore:
        if self.hour_levels.empty():
            return None
        return self.hour_levels.popleft()

    def top_hour_levels(self) -> HourlyLevelScore | None:
        if self.hour_levels.empty():  # if deque is empty
            return None
        return self.hour_levels[0]
    
    def push_hour_levels(self, hour: HourlyLevelScore) -> None:
        if not self.hour_levels.full():
            self.hour_levels.append(hour)
        return        

    def update_hour_levels(self, hour: HourlyLevelScore):
        togo: HourlyLevelScore = self.pop_hour_levels() if self.hour_levels.full() else None

        self.push_hour_levels(hour)

        # update the absolute_score
        self._update_score(togo = togo, new = hour)

        # update the count
        self._update_count(togo = togo, new = hour)

        # update the timestamp
        self._update_timestamp(togo = togo, new = hour)
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
