import React from "react";
import { cn } from "@/lib/utils";

type SentimentLabel = "Bullish" | "Neutral" | "Bearish";

type SentimentRow = {
  symbol: string;
  name: string;
  score: number; // -1 .. 1
  sentiment: SentimentLabel;
  keywords: string[];
};

const DUMMY_SENTIMENT_DATA: SentimentRow[] = [
  {
    symbol: "AAPL",
    name: "Apple",
    score: 0.62,
    sentiment: "Bullish",
    keywords: ["iPhone demand", "services growth", "buybacks"],
  },
  {
    symbol: "MSFT",
    name: "Microsoft",
    score: 0.48,
    sentiment: "Bullish",
    keywords: ["AI tailwind", "Azure", "enterprise"],
  },
  {
    symbol: "NVDA",
    name: "NVIDIA",
    score: 0.71,
    sentiment: "Bullish",
    keywords: ["AI chips", "datacenter", "guidance"],
  },
  {
    symbol: "GOOGL",
    name: "Alphabet",
    score: 0.12,
    sentiment: "Neutral",
    keywords: ["ads", "cloud", "regulation"],
  },
  {
    symbol: "META",
    name: "Meta Platforms",
    score: 0.28,
    sentiment: "Bullish",
    keywords: ["ad recovery", "reels", "efficiency"],
  },
  {
    symbol: "AMZN",
    name: "Amazon",
    score: 0.22,
    sentiment: "Bullish",
    keywords: ["AWS", "retail margin", "prime"],
  },
  {
    symbol: "TSLA",
    name: "Tesla",
    score: -0.14,
    sentiment: "Neutral",
    keywords: ["deliveries", "pricing", "competition"],
  },
  {
    symbol: "ORCL",
    name: "Oracle",
    score: -0.46,
    sentiment: "Bearish",
    keywords: ["missed revenue", "AI spend", "cloud growth"],
  },
  {
    symbol: "INTC",
    name: "Intel",
    score: -0.31,
    sentiment: "Bearish",
    keywords: ["execution risk", "foundry", "margins"],
  },
  {
    symbol: "JPM",
    name: "JPMorgan Chase",
    score: 0.18,
    sentiment: "Bullish",
    keywords: ["NII", "credit quality", "buybacks"],
  },
  {
    symbol: "BAC",
    name: "Bank of America",
    score: 0.06,
    sentiment: "Neutral",
    keywords: ["rates", "deposits", "NII"],
  },
  {
    symbol: "WFC",
    name: "Wells Fargo",
    score: 0.09,
    sentiment: "Neutral",
    keywords: ["efficiency", "regulatory", "NII"],
  },
  {
    symbol: "C",
    name: "Citigroup",
    score: -0.08,
    sentiment: "Neutral",
    keywords: ["restructuring", "costs", "ROE"],
  },
  {
    symbol: "HSBC",
    name: "HSBC",
    score: 0.04,
    sentiment: "Neutral",
    keywords: ["buybacks", "Asia", "rates"],
  },
  {
    symbol: "MA",
    name: "Mastercard",
    score: 0.33,
    sentiment: "Bullish",
    keywords: ["spending", "cross-border", "network"],
  },
  {
    symbol: "V",
    name: "Visa",
    score: 0.29,
    sentiment: "Bullish",
    keywords: ["payments", "volume growth", "travel"],
  },
  {
    symbol: "BRK.B",
    name: "Berkshire Hathaway",
    score: -0.05,
    sentiment: "Neutral",
    keywords: ["cash pile", "portfolio", "insurance"],
  },
  {
    symbol: "AVGO",
    name: "Broadcom",
    score: 0.41,
    sentiment: "Bullish",
    keywords: ["AI networking", "VMware", "guidance"],
  },
  {
    symbol: "WMT",
    name: "Walmart",
    score: -0.02,
    sentiment: "Neutral",
    keywords: ["consumer", "pricing", "margin"],
  },
  {
    symbol: "DIS",
    name: "Disney",
    score: 0.15,
    sentiment: "Bullish",
    keywords: ["streaming", "parks", "cost cuts"],
  },
];

function sentimentStyles(label: SentimentLabel) {
  if (label === "Bullish") return "text-emerald-400";
  if (label === "Bearish") return "text-red-400";
  return "text-gray-300";
}

function scorePill(score: number) {
  // keep it subtle to match your UI
  if (score >= 0.2)
    return "bg-emerald-500/10 text-emerald-300 border-emerald-500/20";
  if (score <= -0.2) return "bg-red-500/10 text-red-300 border-red-500/20";
  return "bg-white/5 text-gray-200 border-white/10";
}

interface SentimentMonitorProps {
  title?: string;
  height?: number;
  className?: string;
  data?: SentimentRow[];
}

const SentimentMonitor = ({
  title = "Sentiment Monitor",
  height = 600,
  className,
  data = DUMMY_SENTIMENT_DATA,
}: SentimentMonitorProps) => {
  return (
    <div className="w-full">
      {title && (
        <h3 className="font-semibold text-2xl text-gray-100 mb-5">{title}</h3>
      )}

      {/* SAME SHELL AS TRADINGVIEW + LIGHT BORDER */}
      <div
        className={cn(
          "tradingview-widget-container border border-gray-600 rounded-lg overflow-hidden",
          className
        )}
        style={{ height }} // IMPORTANT: fixes exact height
      >
        <div className="h-full w-full flex flex-col bg-gray-800/0">
          {/* header row */}
          <div className="px-4 py-3 border-b border-gray-600 text-xs uppercase tracking-wider text-gray-400 grid grid-cols-12 gap-3">
            <div className="col-span-5">Stock</div>
            <div className="col-span-2">Sentiment</div>
            <div className="col-span-2">Score</div>
            <div className="col-span-3">Keywords</div>
          </div>

          {/* body (scrollable) */}
          <div className="flex-1 overflow-y-auto scrollbar-hide-default">
            {data.map((row) => (
              <div
                key={row.symbol}
                className="px-4 py-3 border-b border-white/5 grid grid-cols-12 gap-3 items-center hover:bg-white/5 transition"
              >
                <div className="col-span-5 flex items-center gap-3 min-w-0">
                  <div className="text-gray-200 font-semibold">
                    {row.symbol}
                  </div>
                  <div className="text-gray-400 truncate">{row.name}</div>
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
                  >
                    {row.score >= 0 ? "+" : ""}
                    {row.score.toFixed(2)}
                  </span>
                </div>

                <div className="col-span-3 flex flex-wrap gap-2">
                  {row.keywords.slice(0, 3).map((k) => (
                    <span
                      key={k}
                      className="text-xs px-2 py-1 rounded-md bg-white/5 border border-white/10 text-gray-300"
                    >
                      {k}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {/* footer */}
          <div className="px-4 py-2 text-xs text-gray-500 border-t border-gray-600">
            Dummy data for now — will be replaced by your sentiment pipeline
            output.
          </div>
        </div>
      </div>
    </div>
  );
};

export default SentimentMonitor;
