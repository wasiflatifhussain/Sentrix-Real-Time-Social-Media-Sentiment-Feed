import type {
  SentrixLatestSignalsResponse,
  SentrixTickersResponse,
} from "@/types/sentrix";

const API_BASE =
  process.env.NEXT_PUBLIC_SENTRIX_API_BASE_URL ?? "http://localhost:8000/api/v1";

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Sentrix API ${res.status}: ${text || res.statusText}`);
  }
  return (await res.json()) as T;
}

export async function fetchTickers(limit = 200): Promise<SentrixTickersResponse> {
  return fetchJson<SentrixTickersResponse>(`${API_BASE}/tickers?limit=${limit}`, {
    cache: "no-store",
  });
}

export async function fetchLatestSignals(
  tickers: string[]
): Promise<SentrixLatestSignalsResponse> {
  return fetchJson<SentrixLatestSignalsResponse>(`${API_BASE}/signals/latest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tickers }),
    cache: "no-store",
  });
}
