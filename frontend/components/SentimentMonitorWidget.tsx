"use client";

import SentimentMonitor, {
  SentimentLabel,
  SentimentRow,
} from "@/components/SentimentMonitor";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  fetchLatestSignals,
  fetchTickers,
} from "@/lib/actions/sentrix.actions";
import { DEFAULT_WATCHLIST, TICKER_NAME_MAP } from "@/lib/tickers";
import { cn } from "@/lib/utils";
import { loadWatchlist, saveWatchlist } from "@/lib/watchlist.storage";
import { useEffect, useMemo, useRef, useState } from "react";

function labelFromScore(score: number): SentimentLabel {
  if (score >= 0.2) return "Bullish";
  if (score <= -0.2) return "Bearish";
  return "Neutral";
}

function normalizeMonitorScore(score: number, ticker: string): number {
  if (score !== 0) return score;
  const seed = ticker
    .split("")
    .reduce((acc, ch) => acc + ch.charCodeAt(0), 0);
  return seed % 2 === 0 ? 0.01 : -0.01;
}

function formatTime(tsMs: number) {
  return new Date(tsMs).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function toErrorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  if (typeof err === "string") return err;
  try {
    return JSON.stringify(err);
  } catch {
    return "Unknown error";
  }
}

/**
 * Returns milliseconds until the next boundary of `periodMs`, anchored to Unix epoch.
 * This keeps polling on a fixed schedule and does not shift when users manually refresh.
 */
function msUntilNextBoundary(periodMs: number) {
  const now = Date.now();
  const next = Math.ceil(now / periodMs) * periodMs;
  return next - now;
}

/**
 * Logs a message with SentimentMonitor prefix.
 */
function logSentiment(message: string) {
  console.log(`[SentimentMonitor] ${message}`);
}

export default function SentimentMonitorWidget({
  height = 600,
  className,
  pollMs = 5 * 60_000,
}: {
  height?: number;
  className?: string;
  pollMs?: number; // default: 5 minutes
}) {
  const [availableTickers, setAvailableTickers] = useState<string[]>([]);
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [rows, setRows] = useState<SentimentRow[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [lastFetchedAt, setLastFetchedAt] = useState<number | null>(null);

  const watchlistRef = useRef<string[]>([]);
  const inFlightRef = useRef(false);
  const pollTimeout = useRef<number | null>(null);

  useEffect(() => {
    watchlistRef.current = watchlist;
  }, [watchlist]);

  const addableTickers = useMemo(() => {
    const s = new Set(watchlist);
    return availableTickers.filter((t) => !s.has(t));
  }, [availableTickers, watchlist]);

  async function refreshSignals(nextWatchlist?: string[]) {
    const wl = nextWatchlist ?? watchlistRef.current;

    if (wl.length === 0) {
      setRows([]);
      return;
    }

    if (inFlightRef.current) return;
    inFlightRef.current = true;

    logSentiment(
      `Fetching signals for ${wl.length} tickers (${wl.join(", ")})`
    );

    setLoading(true);
    setErr(null);

    try {
      const resp = await fetchLatestSignals(wl);

      const nextRows: SentimentRow[] = wl.map((ticker) => {
        const doc = resp.signals[ticker];
        const score = normalizeMonitorScore(doc?.signalScore ?? 0, ticker);

        return {
          symbol: ticker,
          name: TICKER_NAME_MAP[ticker] ?? ticker,
          score,
          sentiment: labelFromScore(score),
          keywords: doc?.keywords ?? [],
          updatedAtUtc: doc?.updatedAtUtc,
        };
      });

      // nextRows.sort((a, b) => Math.abs(b.score) - Math.abs(a.score));
      setRows(nextRows);
      setLastFetchedAt(Date.now());
      logSentiment(
        `Fetch completed successfully at ${new Date().toISOString()}`
      );
    } catch (e: unknown) {
      logSentiment(`Fetch failed: ${toErrorMessage(e)}`);
      setErr(toErrorMessage(e) || "Failed to fetch signals");
    } finally {
      setLoading(false);
      inFlightRef.current = false;
    }
  }

  // initial load: tickers + watchlist, then first fetch
  useEffect(() => {
    let mounted = true;

    async function init() {
      try {
        const tickersResp = await fetchTickers(200);
        if (!mounted) return;

        setAvailableTickers(tickersResp.tickers);

        const wl = loadWatchlist(DEFAULT_WATCHLIST).filter((t) =>
          tickersResp.tickers.includes(t)
        );

        setWatchlist(wl);
        saveWatchlist(wl);

        await refreshSignals(wl);
      } catch (e: unknown) {
        setErr(toErrorMessage(e) || "Failed to initialize Sentiment Monitor");
      }
    }

    init();
    return () => {
      mounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // polling: fixed boundary schedule (e.g. every 5 minutes on :00/:05/:10...)
  useEffect(() => {
    function scheduleNext() {
      const waitMs = msUntilNextBoundary(pollMs);

      const nextAt = new Date(Date.now() + waitMs);

      logSentiment(`Next auto-refresh scheduled at ${nextAt.toISOString()}`);

      pollTimeout.current = window.setTimeout(async () => {
        await refreshSignals();
        scheduleNext();
      }, waitMs);
    }

    scheduleNext();

    return () => {
      if (pollTimeout.current) window.clearTimeout(pollTimeout.current);
      pollTimeout.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pollMs]);

  function addTicker(ticker: string) {
    if (watchlist.includes(ticker)) return;
    const next = [...watchlist, ticker];
    setWatchlist(next);
    saveWatchlist(next);
    refreshSignals(next);
  }

  function removeTicker(ticker: string) {
    const next = watchlist.filter((t) => t !== ticker);
    setWatchlist(next);
    saveWatchlist(next);
    refreshSignals(next);
  }

  return (
    <div className={cn("w-full", className)}>
      <div className="mb-3 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex flex-col">
          <h3 className="font-semibold text-xl lg:text-2xl text-gray-100">
            Sentiment Monitor
          </h3>
          {lastFetchedAt ? (
            <div className="text-xs text-gray-400 mt-1">
              Last fetched: {formatTime(lastFetchedAt)}
            </div>
          ) : null}
        </div>

        <div className="flex w-full flex-wrap items-center gap-2 lg:w-auto lg:justify-end">
          <Popover open={pickerOpen} onOpenChange={setPickerOpen}>
            <PopoverTrigger asChild>
              <Button
                variant="outline"
                className="h-9 border-gray-600 bg-transparent text-gray-200 hover:bg-white/5"
              >
                + Add ticker
              </Button>
            </PopoverTrigger>

            <PopoverContent
              align="end"
              className="p-0 w-[min(18rem,calc(100vw-2rem))] overflow-hidden border border-gray-600 bg-[#0b1220] text-gray-200 shadow-xl"
            >
              <Command className="bg-transparent text-gray-200 [&_[cmdk-input-wrapper]]:border-b [&_[cmdk-input-wrapper]]:border-gray-600 [&_[cmdk-input-wrapper]]:bg-transparent [&_[cmdk-list]]:bg-transparent [&_[cmdk-group-heading]]:text-gray-500">
                <CommandInput
                  placeholder="Search ticker..."
                  className="text-gray-200 placeholder:text-gray-500 focus-visible:ring-0 focus-visible:ring-offset-0"
                />
                <CommandEmpty className="text-gray-400">
                  No tickers found.
                </CommandEmpty>

                <CommandGroup className="max-h-[220px] overflow-y-auto bg-transparent">
                  {addableTickers.map((ticker) => (
                    <CommandItem
                      key={ticker}
                      value={ticker}
                      onSelect={() => {
                        addTicker(ticker);
                        setPickerOpen(false);
                      }}
                      className={cn(
                        "cursor-pointer bg-transparent text-gray-200",
                        "aria-selected:bg-white/10 aria-selected:text-gray-100",
                        "data-[selected=true]:bg-white/10 data-[selected=true]:text-gray-100",
                        "hover:bg-white/5"
                      )}
                    >
                      <span className="font-semibold">{ticker}</span>
                      <span className="ml-2 text-gray-400 truncate">
                        {TICKER_NAME_MAP[ticker] ?? ""}
                      </span>
                    </CommandItem>
                  ))}
                </CommandGroup>
              </Command>
            </PopoverContent>
          </Popover>

          <Button
            variant="outline"
            className="h-9 border-gray-600 bg-transparent text-gray-200 hover:bg-white/5"
            onClick={() => refreshSignals()}
            disabled={loading}
          >
            {loading ? "Refreshing..." : "Refresh"}
          </Button>
        </div>
      </div>

      {err ? <div className="mb-3 text-sm text-red-300">{err}</div> : null}

      <SentimentMonitor
        title={""}
        height={height}
        data={rows}
        onRemove={removeTicker}
        footerText={
          watchlist.length === 0
            ? "Add a ticker to start monitoring sentiment."
            : "Backend-powered signal snapshots. Keywords appear when available."
        }
      />

      {/* Optional chips: remove later if table remove is enough */}
      {watchlist.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {watchlist.map((t) => (
            <button
              key={t}
              onClick={() => removeTicker(t)}
              className="text-xs px-2.5 py-1.5 rounded-md bg-white/5 border border-white/10 text-gray-300 hover:bg-white/10"
              title="Remove from watchlist"
            >
              {t} ✕
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
