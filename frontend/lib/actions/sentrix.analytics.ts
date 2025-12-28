import type { SentrixTickerSentimentResponse } from "@/types/sentrix";

const API_BASE =
  process.env.NEXT_PUBLIC_SENTRIX_API_BASE_URL ??
  "http://localhost:8000/api/v1";

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Sentrix API ${res.status}: ${text || res.statusText}`);
  }
  return res.json();
}

export async function fetchWeeklySentiment(
  ticker: string,
  hours = 168
): Promise<SentrixTickerSentimentResponse> {
  // hours is passed to backend as-is
  return fetchJson(`${API_BASE}/tickers/${ticker}/sentiment?hours=${hours}`);
}
