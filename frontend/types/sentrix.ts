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
