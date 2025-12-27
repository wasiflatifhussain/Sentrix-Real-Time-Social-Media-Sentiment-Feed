const KEY = "sentrix.watchlist.v1";

export function loadWatchlist(fallback: string[] = []): string[] {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return fallback;
    return parsed.filter((x) => typeof x === "string");
  } catch {
    return fallback;
  }
}

export function saveWatchlist(tickers: string[]) {
  if (typeof window === "undefined") return;
  localStorage.setItem(KEY, JSON.stringify(tickers));
}
