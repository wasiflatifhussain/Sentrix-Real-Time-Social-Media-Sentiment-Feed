"use client";

import SentimentMonitor, { SentimentLabel, SentimentRow } from "@/components/SentimentMonitor";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
} from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { fetchLatestSignals, fetchTickers } from "@/lib/actions/sentrix.actions";
import { cn } from "@/lib/utils";
import { loadWatchlist, saveWatchlist } from "@/lib/watchlist.storage";
import { useEffect, useMemo, useRef, useState } from "react";

const DEFAULT_WATCHLIST = ["TSLA", "AAPL", "NVDA"];

// optional nice names for the 20 tickers
const TICKER_NAME_MAP: Record<string, string> = {
  AAPL: "Apple",
  AMZN: "Amazon",
  AVGO: "Broadcom",
  "BRK.B": "Berkshire Hathaway",
  COST: "Costco",
  GOOGL: "Alphabet",
  JNJ: "Johnson & Johnson",
  JPM: "JPMorgan Chase",
  LLY: "Eli Lilly",
  MA: "Mastercard",
  META: "Meta Platforms",
  MSFT: "Microsoft",
  NKE: "Nike",
  NVDA: "NVIDIA",
  ORCL: "Oracle",
  PFE: "Pfizer",
  TSLA: "Tesla",
  V: "Visa",
  WMT: "Walmart",
  XOM: "Exxon Mobil",
};

function labelFromScore(score: number): SentimentLabel {
  if (score >= 0.2) return "Bullish";
  if (score <= -0.2) return "Bearish";
  return "Neutral";
}

export default function SentimentMonitorWidget({
  height = 600,
  className,
  pollMs = 60_000,
}: {
  height?: number;
  className?: string;
  pollMs?: number;
}) {
  const [availableTickers, setAvailableTickers] = useState<string[]>([]);
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [rows, setRows] = useState<SentimentRow[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const pollTimer = useRef<number | null>(null);

  const addableTickers = useMemo(() => {
    const s = new Set(watchlist);
    return availableTickers.filter((t) => !s.has(t));
  }, [availableTickers, watchlist]);

  async function refreshSignals(nextWatchlist?: string[]) {
    const wl = nextWatchlist ?? watchlist;
    if (wl.length === 0) {
      setRows([]);
      return;
    }

    setLoading(true);
    setErr(null);
    try {
      const resp = await fetchLatestSignals(wl);
      const nextRows: SentimentRow[] = wl.map((ticker) => {
        const doc = resp.signals[ticker];
        const score = doc?.signalScore ?? 0;

        return {
          symbol: ticker,
          name: TICKER_NAME_MAP[ticker] ?? ticker,
          score,
          sentiment: labelFromScore(score),
          keywords: doc?.keywords ?? [], // backend supports keywords; may be missing in early docs
          updatedAtUtc: doc?.updatedAtUtc,
        };
      });

      // sort: bullish first, then neutral, then bearish OR just by abs(score) - your choice
      nextRows.sort((a, b) => Math.abs(b.score) - Math.abs(a.score));

      setRows(nextRows);
    } catch (e: any) {
      setErr(e?.message ?? "Failed to fetch signals");
    } finally {
      setLoading(false);
    }
  }

  // load tickers + watchlist once
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

        // immediate fetch
        await refreshSignals(wl);
      } catch (e: any) {
        setErr(e?.message ?? "Failed to initialize Sentiment Monitor");
      }
    }

    init();

    return () => {
      mounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // polling
  useEffect(() => {
    if (pollTimer.current) window.clearInterval(pollTimer.current);
    pollTimer.current = window.setInterval(() => {
      refreshSignals();
    }, pollMs);

    return () => {
      if (pollTimer.current) window.clearInterval(pollTimer.current);
      pollTimer.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pollMs, watchlist]);

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
      {/* Top row: title + picker + refresh state */}
      <div className="flex items-center justify-between mb-4 gap-3">
        <h3 className="font-semibold text-2xl text-gray-100">Sentiment Monitor</h3>

        <div className="flex items-center gap-2">
          <Popover open={pickerOpen} onOpenChange={setPickerOpen}>
            <PopoverTrigger asChild>
              <Button variant="outline" className="border-gray-600 bg-transparent text-gray-200 hover:bg-white/5">
                + Add ticker
              </Button>
            </PopoverTrigger>

            <PopoverContent className="p-0 w-72" align="end">
              <Command>
                <CommandInput placeholder="Search ticker..." />
                <CommandEmpty>No tickers found.</CommandEmpty>
                <CommandGroup>
                  {addableTickers.map((ticker) => (
                    <CommandItem
                      key={ticker}
                      value={ticker}
                      onSelect={() => {
                        addTicker(ticker);
                        setPickerOpen(false);
                      }}
                    >
                      <span className="font-semibold text-gray-100">{ticker}</span>
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
            className="border-gray-600 bg-transparent text-gray-200 hover:bg-white/5"
            onClick={() => refreshSignals()}
            disabled={loading}
          >
            {loading ? "Refreshing..." : "Refresh"}
          </Button>
        </div>
      </div>

      {/* error line */}
      {err ? (
        <div className="mb-3 text-sm text-red-300">
          {err}
        </div>
      ) : null}

      {/* Sentiment table */}
      <SentimentMonitor
        title={""} // title already rendered above
        height={height}
        data={rows}
        footerText={
          watchlist.length === 0
            ? "Add a ticker to start monitoring sentiment."
            : "Backend-powered signal snapshots. Keywords appear when available."
        }
      />

      {/* Optional: remove controls (simple) */}
      {watchlist.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {watchlist.map((t) => (
            <button
              key={t}
              onClick={() => removeTicker(t)}
              className="text-xs px-2 py-1 rounded-md bg-white/5 border border-white/10 text-gray-300 hover:bg-white/10"
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
