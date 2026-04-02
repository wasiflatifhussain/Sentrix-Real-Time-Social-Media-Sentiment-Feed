"use client";

import { useEffect, useState } from "react";

import { fetchTickers } from "@/lib/actions/sentrix.actions";
import { fetchWeeklySentiment } from "@/lib/actions/sentrix.analytics";
import { TICKER_NAME_MAP } from "@/lib/tickers";
import { cn } from "@/lib/utils";

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

import SentimentTimeSeriesChart, {
  SentimentChartPoint,
} from "@/components/SentimentTimeSeriesChart";
import PerformanceEvaluationNotebook from "@/components/PerformanceEvaluationNotebook";
import Spinner from "@/components/Spinner";

const DEFAULT_TICKER = "AAPL";

const RANGE_OPTIONS = [
  { label: "12H", hours: 12 },
  { label: "1D", hours: 24 },
  { label: "2D", hours: 48 },
  { label: "7D", hours: 168 },
];

export default function SentimentAnalyticsPage() {
  const [tickers, setTickers] = useState<string[]>([]);
  const [ticker, setTicker] = useState(DEFAULT_TICKER);
  const [hours, setHours] = useState(168);

  const [pickerOpen, setPickerOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [data, setData] = useState<SentimentChartPoint[]>([]);
  const [activeEvaluation, setActiveEvaluation] = useState<
    "ingestor" | "sentiment" | "filtering"
  >("ingestor");

  useEffect(() => {
    fetchTickers(200)
      .then((r) => setTickers(r.tickers))
      .catch(() => setTickers([]));
  }, []);

  useEffect(() => {
    let mounted = true;

    setLoading(true);
    setError(null);

    fetchWeeklySentiment(ticker, hours)
      .then((res) => {
        if (!mounted) return;

        // backend gives SECONDS → normalize once to ms
        const points: SentimentChartPoint[] = res.hourly.map((h) => ({
          timeMs: h.hourStartUtc * 1000,
          avg: h.count > 0 ? h.scoreSum / h.count : 0,
          volume: h.count,
        }));

        // Debug: log fetched points
        const min = Math.min(...points.map((p) => p.timeMs));
        const max = Math.max(...points.map((p) => p.timeMs));
        console.log("hours param =", hours);
        console.log("points =", points.length);
        console.log(
          "min =",
          new Date(min).toISOString(),
          "max =",
          new Date(max).toISOString()
        );

        setData(points);
      })
      .catch((e) => setError(e?.message ?? "Failed to load sentiment"))
      .finally(() => setLoading(false));

    return () => {
      mounted = false;
    };
  }, [ticker, hours]);

  return (
    <div className="py-4 sm:py-8">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-4 sm:mb-6">
        <div className="min-w-0">
          <h1 className="text-2xl sm:text-3xl font-semibold text-gray-100">
            Sentiment Analytics
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            Hourly sentiment evolution over time
          </p>
        </div>

        <div className="flex items-center gap-2 sm:gap-3">
          <p className="text-sm text-white/50 hidden md:block">
            Click to change ticker
          </p>

          <Popover open={pickerOpen} onOpenChange={setPickerOpen}>
            <PopoverTrigger asChild>
              <Button
                variant="outline"
                className="border-gray-600 bg-transparent text-gray-200 hover:bg-white/5"
              >
                {ticker} — {TICKER_NAME_MAP[ticker] ?? "Unknown"}
              </Button>
            </PopoverTrigger>

            <PopoverContent
              align="end"
              className="p-0 w-[min(20rem,calc(100vw-2rem))] border border-gray-600 bg-[#0b1220]"
            >
              <Command className="bg-transparent text-gray-200">
                <CommandInput placeholder="Search ticker..." />
                <CommandEmpty>No tickers found.</CommandEmpty>
                <CommandGroup>
                  {tickers.map((t) => (
                    <CommandItem
                      key={t}
                      value={t}
                      onSelect={() => {
                        setTicker(t);
                        setPickerOpen(false);
                      }}
                    >
                      <span className="font-semibold">{t}</span>
                      <span className="ml-2 text-gray-400 truncate">
                        {TICKER_NAME_MAP[t] ?? ""}
                      </span>
                    </CommandItem>
                  ))}
                </CommandGroup>
              </Command>
            </PopoverContent>
          </Popover>
        </div>
      </div>

      <div className="mb-4 grid grid-cols-4 gap-2 sm:flex sm:flex-wrap">
        {RANGE_OPTIONS.map((r) => (
          <button
            key={r.hours}
            onClick={() => setHours(r.hours)}
            className={cn(
              "h-9 px-2 sm:px-3 text-xs sm:text-sm rounded-md border transition",
              hours === r.hours
                ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/30"
                : "bg-white/5 text-gray-300 border-white/10 hover:bg-white/10"
            )}
          >
            {r.label}
          </button>
        ))}
      </div>

      <div className="border border-gray-600 rounded-lg p-3 sm:p-4 bg-black/30 min-h-[360px] sm:min-h-[420px]">
        {loading ? (
          <div className="flex items-center justify-center h-[320px] sm:h-[380px]">
            <Spinner />
          </div>
        ) : error ? (
          <div className="text-red-400 text-sm">{error}</div>
        ) : (
          <SentimentTimeSeriesChart data={data} />
        )}
      </div>

      <section className="mt-8 sm:mt-10">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-xl sm:text-2xl font-semibold text-gray-100">
              Performance Evaluation
            </h2>
            <p className="mt-1 text-sm text-gray-400">
              Notebook-style demo for service-level evaluation metrics
            </p>
          </div>
          <div className="flex w-full flex-wrap gap-2 sm:w-auto">
            <button
              onClick={() => setActiveEvaluation("ingestor")}
              className={cn(
                "h-9 px-3 text-xs sm:text-sm rounded-md border transition",
                activeEvaluation === "ingestor"
                  ? "bg-cyan-500/10 text-cyan-300 border-cyan-500/40"
                  : "bg-white/5 text-gray-300 border-white/10 hover:bg-white/10"
              )}
            >
              Ingestor Service
            </button>
            <button
              onClick={() => setActiveEvaluation("filtering")}
              className={cn(
                "h-9 px-3 text-xs sm:text-sm rounded-md border transition",
                activeEvaluation === "filtering"
                  ? "bg-cyan-500/10 text-cyan-300 border-cyan-500/40"
                  : "bg-white/5 text-gray-300 border-white/10 hover:bg-white/10"
              )}
            >
              Filtering Services
            </button>
            <button
              onClick={() => setActiveEvaluation("sentiment")}
              className={cn(
                "h-9 px-3 text-xs sm:text-sm rounded-md border transition",
                activeEvaluation === "sentiment"
                  ? "bg-cyan-500/10 text-cyan-300 border-cyan-500/40"
                  : "bg-white/5 text-gray-300 border-white/10 hover:bg-white/10"
              )}
            >
              Sentiment Service
            </button>
          </div>
        </div>

        <div className="rounded-lg border border-gray-600 bg-gradient-to-b from-teal-400/5 to-black/30 p-3 sm:p-4 shadow-[0_0_0_1px_rgba(15,237,190,0.06),0_14px_30px_-20px_rgba(15,237,190,0.35)]">
          {activeEvaluation === "ingestor" ? (
            <PerformanceEvaluationNotebook />
          ) : (
            <div className="min-h-[120px]" />
          )}
        </div>
      </section>
    </div>
  );
}
