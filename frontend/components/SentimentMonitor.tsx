import { cn } from "@/lib/utils";

export type SentimentLabel = "Bullish" | "Neutral" | "Bearish";

export type SentimentRow = {
  symbol: string;
  name?: string;
  score: number; // -1 .. 1
  sentiment: SentimentLabel;
  keywords?: string[];
  updatedAtUtc?: number;
};

function sentimentStyles(label: SentimentLabel) {
  if (label === "Bullish") return "text-emerald-400";
  if (label === "Bearish") return "text-red-400";
  return "text-gray-300";
}

function scorePill(score: number) {
  if (score >= 0.2)
    return "bg-emerald-500/10 text-emerald-300 border-emerald-500/20";
  if (score <= -0.2) return "bg-red-500/10 text-red-300 border-red-500/20";
  return "bg-white/5 text-gray-200 border-white/10";
}

interface SentimentMonitorProps {
  title?: string;
  height?: number;
  className?: string;
  data: SentimentRow[];
  footerText?: string;
  onRemove?: (ticker: string) => void;
}

const SentimentMonitor = ({
  title = "Sentiment Monitor",
  height = 600,
  className,
  data,
  footerText,
  onRemove,
}: SentimentMonitorProps) => {
  return (
    <div className="w-full">
      {title ? (
        <h3 className="font-semibold text-2xl text-gray-100 mb-5">{title}</h3>
      ) : null}

      <div
        className={cn(
          "tradingview-widget-container border border-gray-600 rounded-lg overflow-hidden",
          className
        )}
        style={{ height }}
      >
        <div className="h-full w-full flex flex-col bg-gray-800/0">
          <div className="px-4 py-3 border-b border-gray-600 text-xs uppercase tracking-wider text-gray-400 grid grid-cols-13 gap-3">
            <div className="col-span-5">Stock</div>
            <div className="col-span-2">Sentiment</div>
            <div className="col-span-2">Score</div>
            <div className="col-span-3">Keywords</div>
            <div className="col-span-1 text-right">Actions</div>
          </div>

          <div className="flex-1 overflow-y-auto scrollbar-hide-default">
            {data.length === 0 ? (
              <div className="px-4 py-6 text-sm text-gray-400">
                No tickers in watchlist yet.
              </div>
            ) : (
              data.map((row) => (
                <div
                  key={row.symbol}
                  className="px-4 py-3 border-b border-white/5 grid grid-cols-13 gap-3 items-center hover:bg-white/5 transition"
                >
                  <div className="col-span-5 flex items-center gap-3 min-w-0">
                    <div className="text-gray-200 font-semibold">
                      {row.symbol}
                    </div>
                    <div className="text-gray-400 truncate">
                      {row.name ?? row.symbol}
                    </div>
                  </div>

                  <div
                    className={cn(
                      "col-span-2 font-medium",
                      sentimentStyles(row.sentiment)
                    )}
                  >
                    {row.sentiment}
                  </div>

                  <div className="col-span-2">
                    <span
                      className={cn(
                        "inline-flex items-center rounded-md border px-2 py-1 text-xs font-semibold tabular-nums",
                        scorePill(row.score)
                      )}
                      title={
                        row.updatedAtUtc
                          ? `Updated (UTC): ${new Date(
                              row.updatedAtUtc * 1000
                            ).toISOString()}`
                          : undefined
                      }
                    >
                      {row.score >= 0 ? "+" : ""}
                      {row.score.toFixed(2)}
                    </span>
                  </div>

                  <div className="col-span-3 flex flex-wrap gap-2">
                    {(row.keywords?.length ?? 0) === 0 ? (
                      <span className="text-xs px-2 py-1 rounded-md bg-white/5 border border-white/10 text-gray-400">
                        —
                      </span>
                    ) : (
                      row.keywords!.slice(0, 3).map((k) => (
                        <span
                          key={k}
                          className="text-xs px-2 py-1 rounded-md bg-white/5 border border-white/10 text-gray-300"
                        >
                          {k}
                        </span>
                      ))
                    )}
                  </div>

                  <div className="col-span-1 flex justify-end">
                    {onRemove ? (
                      <button
                        onClick={() => onRemove(row.symbol)}
                      className="text-xs px-2 py-1 rounded-md bg-white/5 border border-white/10 text-gray-300 hover:bg-white/10"
                        title="Remove from watchlist"
                      >
                        Remove
                      </button>
                    ) : null}
                  </div>
                </div>
              ))
            )}
          </div>

          {footerText ? (
            <div className="px-4 py-2 text-xs text-gray-500 border-t border-gray-600">
              {footerText}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
};

export default SentimentMonitor;
