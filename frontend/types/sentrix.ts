export type SentrixTickersResponse = {
  tickers: string[];
  count: number;
};

export type SentrixSignalDoc = {
  _id: string;
  ticker: string;
  signalScore: number;
  asOfHourStartUtc: number;
  createdAtUtc: number;
  updatedAtUtc: number;

  recentVolume?: number; // optional field
  keywords?: string[];
  halfLifeHours?: number;
};

export type SentrixLatestSignalsResponse = {
  requested: string[];
  found: number;
  signals: Record<string, SentrixSignalDoc>;
};

export type SentrixHourlyDoc = {
  _id: string;
  ticker: string;
  hourStartUtc: number;
  hourEndUtc: number;
  count: number;
  scoreSum: number;
  keywordCounts?: Record<string, number>;
  sourceBreakdown?: Record<string, number>;
  updatedAtUtc?: number;
  expireAtUtc?: number;
};

export type SentrixTickerSentimentResponse = {
  ticker: string;
  signal: SentrixSignalDoc | null;
  hourly: SentrixHourlyDoc[];
};
