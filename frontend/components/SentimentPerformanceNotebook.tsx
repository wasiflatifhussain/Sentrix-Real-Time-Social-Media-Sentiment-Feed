"use client";

import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import aaplRaw from "@/data/evaluation/sentiment_aapl_alignment_2026_last_7d_60m.json";
import amznRaw from "@/data/evaluation/sentiment_amzn_alignment_2026_last_7d_60m.json";
import jpmRaw from "@/data/evaluation/sentiment_jpm_alignment_2026_last_7d_60m.json";
import { Button } from "@/components/ui/button";

type Ticker = "AAPL" | "JPM" | "AMZN";
type CellKey = "summary" | "trendChart" | "matchChart";

type SentimentAlignmentRow = {
  timestamp_utc: string;
  ticker: string;
  price_close: number;
  next_price_close: number;
  return_1h_pct: number;
  market_direction: number;
  sentiment_score: number;
  sentiment_direction: number;
  is_match: number;
};

type NotebookRow = SentimentAlignmentRow & {
  label: string;
  day: string;
};

const DATASETS: Record<Ticker, SentimentAlignmentRow[]> = {
  AAPL: aaplRaw as SentimentAlignmentRow[],
  JPM: jpmRaw as SentimentAlignmentRow[],
  AMZN: amznRaw as SentimentAlignmentRow[],
};

const PYTHON_KEYWORDS = new Set([
  "import",
  "as",
  "display",
  "read_csv",
  "to_datetime",
  "sort_values",
  "groupby",
  "mean",
  "sum",
  "round",
  "set_title",
  "set_ylabel",
  "set_xlabel",
  "legend",
]);

function formatHourLabel(iso: string) {
  const d = new Date(iso);
  const month = d.toLocaleString("en-US", { month: "short", timeZone: "UTC" });
  const day = d.toLocaleString("en-US", { day: "2-digit", timeZone: "UTC" });
  const hour = d.toLocaleString("en-US", {
    hour: "2-digit",
    hour12: false,
    timeZone: "UTC",
  });
  return `${month} ${day} ${hour}:00`;
}

function formatDay(iso: string) {
  return new Date(iso).toLocaleDateString("en-CA", { timeZone: "UTC" });
}

function codeSnippets(ticker: Ticker): Record<CellKey, string> {
  const lower = ticker.toLowerCase();
  return {
    summary: `# Cell [1] - ${ticker} directional alignment summary
import pandas as pd

df = pd.read_csv("frontend/data/evaluation/sentiment_${lower}_alignment_2026_last_7d_60m.csv")
df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
eval_df = df[df["market_direction"].isin([-1, 1])].copy()

summary = {
  "directional_accuracy_pct": round(eval_df["is_match"].mean() * 100, 2),
  "random_baseline_pct": 50.0,
  "majority_baseline_pct": round((eval_df["market_direction"] == eval_df["market_direction"].mode().iloc[0]).mean() * 100, 2),
}
display(summary)`,
    trendChart: `# Cell [2] - ${ticker} sentiment vs return trend
plot_df = eval_df.sort_values("timestamp_utc").copy()

fig, ax1 = plt.subplots(figsize=(11, 4))
ax1.plot(plot_df["timestamp_utc"], plot_df["sentiment_score"], color="#10B981", linewidth=2)
ax1.axhline(0, linestyle="--", alpha=0.6)

ax2 = ax1.twinx()
ax2.plot(plot_df["timestamp_utc"], plot_df["return_1h_pct"], color="#2563EB", linewidth=1.8)
ax1.set_title("${ticker} Sentiment vs Next-Hour Market Return")
ax1.set_xlabel("Timestamp (UTC)")`,
    matchChart: `# Cell [3] - ${ticker} match/mismatch profile
plot_df = eval_df.sort_values("timestamp_utc").copy()
plot_df["day_utc"] = plot_df["timestamp_utc"].dt.strftime("%Y-%m-%d")

daily = plot_df.groupby("day_utc")["is_match"].agg(["sum", "count"]).reset_index()
daily["mismatch"] = daily["count"] - daily["sum"]
daily["match_pct"] = daily["sum"] / daily["count"] * 100
daily["mismatch_pct"] = daily["mismatch"] / daily["count"] * 100

daily[["day_utc", "match_pct", "mismatch_pct"]]`,
  };
}

function NotebookCell({
  index,
  title,
  code,
  runState,
  onRun,
  children,
}: {
  index: number;
  title: string;
  code: string;
  runState: "idle" | "running" | "done";
  onRun: () => void;
  children: React.ReactNode;
}) {
  const [isCodeExpanded, setIsCodeExpanded] = useState(false);
  const codeLines = code.split("\n");
  const previewLineCount = Math.min(5, codeLines.length);
  const previewSnippet = codeLines.slice(0, previewLineCount).join("\n");
  const continuationSnippet = codeLines.slice(previewLineCount).join("\n");
  const hasContinuation = codeLines.length > previewLineCount;

  return (
    <section className="rounded-xl border border-gray-600 bg-gradient-to-b from-teal-400/5 via-black/20 to-black/20">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-600 px-3 py-2 sm:px-4">
        <div className="min-w-0">
          <p className="text-[11px] uppercase tracking-wide text-gray-400">Cell [{index}]</p>
          <p className="text-sm font-medium text-gray-100">{title}</p>
        </div>
        <Button
          onClick={onRun}
          disabled={runState === "running"}
          className="h-8 rounded-md border border-teal-400/40 bg-teal-400/10 text-teal-300 hover:bg-teal-400/20"
          variant="outline"
        >
          {runState === "running" ? "Running..." : "Run Cell"}
        </Button>
      </div>

      <CodeBlock snippet={previewSnippet} />
      {hasContinuation && !isCodeExpanded && (
        <div className="border-b border-gray-600 bg-[#121418] font-mono text-[12px] leading-6 text-gray-200 sm:text-[13px]">
          <button
            type="button"
            onClick={() => setIsCodeExpanded(true)}
            className="grid w-full min-w-max grid-cols-[40px_1fr] text-left hover:bg-white/5"
          >
            <span className="select-none border-r border-gray-700 bg-[#0c0f13] px-2 text-right text-gray-500">
              {previewLineCount + 1}
            </span>
            <span className="px-3 text-gray-400 sm:px-4">
              <span className="mr-1 text-gray-300">▶</span>
              ... show continuation
            </span>
          </button>
        </div>
      )}
      {hasContinuation && isCodeExpanded && (
        <>
          <div className="border-b border-gray-600 bg-[#121418] font-mono text-[12px] leading-6 text-gray-200 sm:text-[13px]">
            <button
              type="button"
              onClick={() => setIsCodeExpanded(false)}
              className="grid w-full min-w-max grid-cols-[40px_1fr] text-left hover:bg-white/5"
            >
              <span className="select-none border-r border-gray-700 bg-[#0c0f13] px-2 text-right text-gray-500">
                {previewLineCount + 1}
              </span>
              <span className="px-3 text-gray-400 sm:px-4">
                <span className="mr-1 text-gray-300">▼</span>
                ... hide continuation
              </span>
            </button>
          </div>
          <CodeBlock snippet={continuationSnippet} startLine={previewLineCount + 2} />
        </>
      )}

      <div className="px-3 py-3 sm:px-4">
        {runState === "idle" && (
          <p className="text-xs text-gray-500">Output hidden. Press Run Cell to execute.</p>
        )}
        {runState === "running" && (
          <div className="flex items-center gap-2 text-sm text-teal-300">
            <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-teal-300" />
            Kernel: running...
          </div>
        )}
        {runState === "done" && (
          <div className="space-y-2">
            <p className="text-xs text-gray-500">Out[{index}]: execution completed successfully</p>
            {children}
          </div>
        )}
      </div>
    </section>
  );
}

function CodeBlock({ snippet, startLine = 1 }: { snippet: string; startLine?: number }) {
  const lines = snippet.split("\n");
  return (
    <div className="overflow-x-auto border-b border-gray-600 bg-[#121418]">
      <code className="block min-w-max font-mono text-[12px] leading-6 text-gray-200 sm:text-[13px]">
        {lines.map((line, idx) => (
          <div key={`${idx}-${line}`} className="grid grid-cols-[40px_1fr]">
            <span className="select-none border-r border-gray-700 bg-[#0c0f13] px-2 text-right text-gray-500">
              {startLine + idx}
            </span>
            <span className="px-3 sm:px-4">{highlightPythonLine(line)}</span>
          </div>
        ))}
      </code>
    </div>
  );
}

function highlightPythonLine(line: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  const commentIdx = line.indexOf("#");
  const codePart = commentIdx >= 0 ? line.slice(0, commentIdx) : line;
  const commentPart = commentIdx >= 0 ? line.slice(commentIdx) : "";
  const tokenRegex = /(".*?"|'.*?'|\b\d+(?:\.\d+)?\b|\b[A-Za-z_]\w*\b|[=(),.\[\]-])/g;
  let cursor = 0;
  let match: RegExpExecArray | null;

  while ((match = tokenRegex.exec(codePart)) !== null) {
    const full = match[0];
    const start = match.index;

    if (start > cursor) {
      parts.push(
        <span key={`txt-${cursor}-${start}`} className="text-gray-200">
          {codePart.slice(cursor, start)}
        </span>
      );
    }

    if ((full.startsWith('"') && full.endsWith('"')) || (full.startsWith("'") && full.endsWith("'"))) {
      parts.push(
        <span key={`str-${start}`} className="text-amber-300">
          {full}
        </span>
      );
    } else if (/^\d+(?:\.\d+)?$/.test(full)) {
      parts.push(
        <span key={`num-${start}`} className="text-orange-300">
          {full}
        </span>
      );
    } else if (PYTHON_KEYWORDS.has(full)) {
      parts.push(
        <span key={`kw-${start}`} className="text-sky-300">
          {full}
        </span>
      );
    } else if (full === "df" || full === "eval_df" || full === "summary" || full === "plot_df" || full === "daily") {
      parts.push(
        <span key={`var-${start}`} className="text-teal-300">
          {full}
        </span>
      );
    } else if (/^[=(),.\[\]-]$/.test(full)) {
      parts.push(
        <span key={`pun-${start}`} className="text-gray-400">
          {full}
        </span>
      );
    } else {
      parts.push(
        <span key={`id-${start}`} className="text-gray-200">
          {full}
        </span>
      );
    }

    cursor = start + full.length;
  }

  if (cursor < codePart.length) {
    parts.push(
      <span key={`tail-${cursor}`} className="text-gray-200">
        {codePart.slice(cursor)}
      </span>
    );
  }

  if (commentPart) {
    parts.push(
      <span key="comment" className="text-emerald-400">
        {commentPart}
      </span>
    );
  }

  if (parts.length === 0) {
    parts.push(
      <span key="empty" className="text-gray-200">
        {" "}
      </span>
    );
  }

  return parts;
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-gray-600 bg-gradient-to-b from-teal-400/5 to-black/30 px-3 py-2">
      <p className="text-[11px] uppercase tracking-wide text-gray-500">{label}</p>
      <p className="text-sm font-semibold text-gray-100">{value}</p>
    </div>
  );
}

export default function SentimentPerformanceNotebook() {
  const [selectedTicker, setSelectedTicker] = useState<Ticker>("AAPL");
  const [runStates, setRunStates] = useState<Record<CellKey, "idle" | "running" | "done">>({
    summary: "idle",
    trendChart: "idle",
    matchChart: "idle",
  });

  const snippetMap = useMemo(() => codeSnippets(selectedTicker), [selectedTicker]);

  const rows = useMemo<NotebookRow[]>(
    () =>
      DATASETS[selectedTicker].map((r) => ({
        ...r,
        market_direction: Number(r.market_direction),
        sentiment_score: Number(r.sentiment_score),
        sentiment_direction: Number(r.sentiment_direction),
        return_1h_pct: Number(r.return_1h_pct),
        is_match: Number(r.is_match),
        label: formatHourLabel(r.timestamp_utc),
        day: formatDay(r.timestamp_utc),
      })),
    [selectedTicker]
  );

  const evalRows = useMemo(
    () => rows.filter((r) => r.market_direction === -1 || r.market_direction === 1),
    [rows]
  );

  const summary = useMemo(() => {
    const evalCount = evalRows.length;
    const accuracyPct =
      evalCount > 0 ? (evalRows.reduce((acc, r) => acc + r.is_match, 0) / evalCount) * 100 : 0;

    const majorityDirection = evalCount
      ? evalRows.reduce<Record<string, number>>((acc, r) => {
          acc[r.market_direction] = (acc[r.market_direction] ?? 0) + 1;
          return acc;
        }, {})["1"] >=
        evalRows.reduce<Record<string, number>>((acc, r) => {
          acc[r.market_direction] = (acc[r.market_direction] ?? 0) + 1;
          return acc;
        }, {})["-1"]
        ? 1
        : -1
      : 1;

    const majorityBaselinePct =
      evalCount > 0
        ? (evalRows.filter((r) => r.market_direction === majorityDirection).length / evalCount) *
          100
        : 0;

    return {
      rowsTotal: rows.length,
      rowsEvaluable: evalCount,
      accuracyPct,
      randomBaselinePct: 50,
      majorityBaselinePct,
      upliftRandomPct: accuracyPct - 50,
      upliftMajorityPct: accuracyPct - majorityBaselinePct,
    };
  }, [rows, evalRows]);

  const dailyRows = useMemo(() => {
    const byDay = new Map<string, { day: string; match: number; total: number }>();
    for (const row of evalRows) {
      const existing = byDay.get(row.day) ?? { day: row.day, match: 0, total: 0 };
      existing.total += 1;
      existing.match += row.is_match;
      byDay.set(row.day, existing);
    }
    return Array.from(byDay.values())
      .map((r) => ({
        day: r.day,
        matchPct: (r.match / r.total) * 100,
        mismatchPct: ((r.total - r.match) / r.total) * 100,
      }))
      .sort((a, b) => a.day.localeCompare(b.day));
  }, [evalRows]);

  const runCell = (key: CellKey) => {
    setRunStates((prev) => ({ ...prev, [key]: "running" }));
    setTimeout(() => {
      setRunStates((prev) => ({ ...prev, [key]: "done" }));
    }, 1200);
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor="sentiment-eval-ticker" className="text-xs font-medium text-gray-400">
          Evaluation Ticker
        </label>
        <select
          id="sentiment-eval-ticker"
          value={selectedTicker}
          onChange={(e) => {
            const next = e.target.value as Ticker;
            setSelectedTicker(next);
            setRunStates({ summary: "idle", trendChart: "idle", matchChart: "idle" });
          }}
          className="h-9 rounded-md border border-gray-600 bg-[#0b1220] px-3 text-sm text-gray-200 outline-none transition focus:border-teal-400/50"
        >
          <option value="AAPL">AAPL</option>
          <option value="JPM">JPM</option>
          <option value="AMZN">AMZN</option>
        </select>
      </div>

      <NotebookCell
        index={1}
        title={`${selectedTicker} KPI Table`}
        code={snippetMap.summary}
        runState={runStates.summary}
        onRun={() => runCell("summary")}
      >
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
          <MetricCard label="Rows" value={`${summary.rowsEvaluable}/${summary.rowsTotal}`} />
          <MetricCard label="Accuracy" value={`${summary.accuracyPct.toFixed(2)}%`} />
          <MetricCard label="Random Baseline" value={`${summary.randomBaselinePct.toFixed(2)}%`} />
          <MetricCard
            label="Majority Baseline"
            value={`${summary.majorityBaselinePct.toFixed(2)}%`}
          />
          <MetricCard label="Uplift vs Random" value={`${summary.upliftRandomPct.toFixed(2)} pp`} />
          <MetricCard
            label="Uplift vs Majority"
            value={`${summary.upliftMajorityPct.toFixed(2)} pp`}
          />
        </div>
      </NotebookCell>

      <NotebookCell
        index={2}
        title="Sentiment vs Return Trend"
        code={snippetMap.trendChart}
        runState={runStates.trendChart}
        onRun={() => runCell("trendChart")}
      >
        <div className="h-[240px] w-full sm:h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={evalRows} margin={{ top: 12, right: 16, left: -12, bottom: 30 }}>
              <defs>
                <linearGradient id="sentimentTrendBg" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#0FEDBE" stopOpacity={0.08} />
                  <stop offset="100%" stopColor="#0FEDBE" stopOpacity={0.01} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(255,255,255,0.06)" />
              <XAxis
                dataKey="label"
                tick={{ fill: "#9ca3af", fontSize: 10 }}
                minTickGap={24}
                angle={-25}
                textAnchor="end"
                height={48}
              />
              <YAxis
                yAxisId="sentiment"
                domain={[-1, 1]}
                tick={{ fill: "#9ca3af", fontSize: 10 }}
                label={{
                  value: "Sentiment",
                  angle: -90,
                  position: "insideLeft",
                  fill: "#9ca3af",
                  dx: -2,
                }}
              />
              <YAxis
                yAxisId="returns"
                orientation="right"
                tick={{ fill: "#9ca3af", fontSize: 10 }}
                label={{
                  value: "Return %",
                  angle: 90,
                  position: "insideRight",
                  fill: "#9ca3af",
                  dx: 2,
                }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#0b1220",
                  border: "1px solid #374151",
                  borderRadius: 10,
                }}
              />
              <ReferenceLine yAxisId="sentiment" y={0} stroke="#6b7280" strokeDasharray="5 5" />
              <ReferenceLine yAxisId="returns" y={0} stroke="#475569" strokeDasharray="5 5" />
              <Line
                yAxisId="sentiment"
                type="monotone"
                dataKey="sentiment_score"
                stroke="#10B981"
                strokeWidth={2}
                dot={false}
                name="Sentiment"
              />
              <Line
                yAxisId="returns"
                type="monotone"
                dataKey="return_1h_pct"
                stroke="#2563EB"
                strokeWidth={1.9}
                dot={false}
                name="1h Return %"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </NotebookCell>

      <NotebookCell
        index={3}
        title="Match vs Mismatch"
        code={snippetMap.matchChart}
        runState={runStates.matchChart}
        onRun={() => runCell("matchChart")}
      >
        <div className="grid gap-3 lg:grid-cols-2">
          <div className="h-[220px] w-full sm:h-[250px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={[
                  {
                    bucket: selectedTicker,
                    match: evalRows.reduce((acc, r) => acc + r.is_match, 0),
                    mismatch: evalRows.length - evalRows.reduce((acc, r) => acc + r.is_match, 0),
                  },
                ]}
                margin={{ top: 10, right: 10, left: 0, bottom: 10 }}
              >
                <CartesianGrid stroke="rgba(255,255,255,0.06)" />
                <XAxis dataKey="bucket" tick={{ fill: "#9ca3af", fontSize: 10 }} />
                <YAxis tick={{ fill: "#9ca3af", fontSize: 10 }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#0b1220",
                    border: "1px solid #374151",
                    borderRadius: 10,
                  }}
                />
                <Legend />
                <Bar dataKey="match" stackId="a" fill="#10B981" name="Match" />
                <Bar dataKey="mismatch" stackId="a" fill="#F59E0B" name="Mismatch" />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="h-[220px] w-full sm:h-[250px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={dailyRows} margin={{ top: 10, right: 10, left: -8, bottom: 10 }}>
                <CartesianGrid stroke="rgba(255,255,255,0.06)" />
                <XAxis
                  dataKey="day"
                  tick={{ fill: "#9ca3af", fontSize: 10 }}
                  tickFormatter={(d) => String(d).slice(5)}
                />
                <YAxis domain={[0, 100]} tick={{ fill: "#9ca3af", fontSize: 10 }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#0b1220",
                    border: "1px solid #374151",
                    borderRadius: 10,
                  }}
                />
                <Legend />
                <Bar dataKey="matchPct" stackId="a" fill="#10B981" name="Match %" />
                <Bar dataKey="mismatchPct" stackId="a" fill="#F59E0B" name="Mismatch %" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </NotebookCell>
    </div>
  );
}
