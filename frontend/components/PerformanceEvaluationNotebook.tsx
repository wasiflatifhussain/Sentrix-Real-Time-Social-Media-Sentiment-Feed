"use client";

import { useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import ingestorViewRaw from "@/data/evaluation/ingestor_frontend_view.json";
import { Button } from "@/components/ui/button";

type IngestorChartRow = {
  run_started_at_utc: string;
  label: string;
  run_success_rate_pct: number;
  run_latency_seconds: number;
};

type IngestorSummary = {
  windowStartUtc: string;
  windowDays: number;
  runsObserved: number;
  runsExpected: number;
  coveragePct: number;
  avgRunSuccessRatePct: number;
  weightedSuccessRatePct: number;
  medianLatencySeconds: number;
  p95LatencySeconds: number;
  lessThan3MinPct: number;
  between4And5MinPct: number;
  over5MinCount: number;
};

type IngestorView = {
  summary: IngestorSummary;
  charts: IngestorChartRow[];
};

type CellKey = "summary" | "successChart" | "latencyChart";

const ingestorView = ingestorViewRaw as IngestorView;

const CODE_SNIPPETS: Record<CellKey, string> = {
  summary: `# Cell [1] - KPI summary (manually collected dataset)
import pandas as pd

    precomputed = pd.read_json("frontend/data/evaluation/ingestor_frontend_view.json")
summary = precomputed["summary"]
display(summary)`,
  successChart: `# Cell [2] - Success-rate trend
plot_df = precomputed["charts"]

fig, ax = plt.subplots(figsize=(11, 4))
ax.plot(plot_df["run_started_at_utc"], plot_df["run_success_rate_pct"], color="#0FEDBE", linewidth=2)
ax.set_title("Per-run Success Rate (%)")
ax.set_ylabel("Success %")
ax.set_xlabel("Run Start (UTC)")
ax.grid(alpha=0.15)
plt.tight_layout()`,
  latencyChart: `# Cell [3] - Latency trend
plot_df = precomputed["charts"]

fig, ax = plt.subplots(figsize=(11, 4))
ax.plot(plot_df["run_started_at_utc"], plot_df["run_latency_seconds"], color="#5862FF", linewidth=2)
ax.axhline(180, linestyle="--", color="#22d3ee")  # target threshold
ax.axhline(300, linestyle="--", color="#FDD458")  # upper acceptable bound
ax.set_title("Per-run Latency (seconds)")
ax.set_ylabel("Latency (s)")
ax.set_xlabel("Run Start (UTC)")
ax.grid(alpha=0.15)
plt.tight_layout()`,
};

const PYTHON_KEYWORDS = new Set([
  "display",
  "plot",
  "read_json",
  "axhline",
  "set_title",
]);

function NotebookCell({
  index,
  title,
  cellKey,
  runState,
  onRun,
  children,
}: {
  index: number;
  title: string;
  cellKey: CellKey;
  runState: "idle" | "running" | "done";
  onRun: (key: CellKey) => void;
  children: React.ReactNode;
}) {
  const [isCodeExpanded, setIsCodeExpanded] = useState(false);
  const codeLines = CODE_SNIPPETS[cellKey].split("\n");
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
        <div className="flex items-center gap-2">
          <Button
            onClick={() => onRun(cellKey)}
            disabled={runState === "running"}
            className="h-8 rounded-md border border-teal-400/40 bg-teal-400/10 text-teal-300 hover:bg-teal-400/20"
            variant="outline"
          >
            {runState === "running" ? "Running..." : "Run Cell"}
          </Button>
        </div>
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
    } else if (full === "df" || full === "summary" || full === "ax") {
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

export default function PerformanceEvaluationNotebook() {
  const [runStates, setRunStates] = useState<Record<CellKey, "idle" | "running" | "done">>({
    summary: "idle",
    successChart: "idle",
    latencyChart: "idle",
  });

  const chartRows = ingestorView.charts;
  const summary = ingestorView.summary;

  const runCell = (key: CellKey) => {
    setRunStates((prev) => ({ ...prev, [key]: "running" }));
    setTimeout(() => {
      setRunStates((prev) => ({ ...prev, [key]: "done" }));
    }, 1200);
  };

  return (
    <div className="space-y-4">
      <NotebookCell
        index={1}
        title="Ingestor KPI Table"
        cellKey="summary"
        runState={runStates.summary}
        onRun={runCell}
      >
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
          <MetricCard label="Runs" value={`${summary.runsObserved}/${summary.runsExpected}`} />
          <MetricCard label="Coverage" value={`${summary.coveragePct.toFixed(2)}%`} />
          <MetricCard label="Avg Success" value={`${summary.avgRunSuccessRatePct.toFixed(2)}%`} />
          <MetricCard
            label="Weighted Success"
            value={`${summary.weightedSuccessRatePct.toFixed(2)}%`}
          />
          <MetricCard label="Median Latency" value={`${summary.medianLatencySeconds.toFixed(1)}s`} />
          <MetricCard label="P95 Latency" value={`${summary.p95LatencySeconds.toFixed(1)}s`} />
        </div>
      </NotebookCell>

      <NotebookCell
        index={2}
        title="Success Rate Trend"
        cellKey="successChart"
        runState={runStates.successChart}
        onRun={runCell}
      >
        <div className="h-[240px] w-full sm:h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartRows} margin={{ top: 12, right: 12, left: 18, bottom: 42 }}>
              <defs>
                <linearGradient id="evalSuccessBg" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#0FEDBE" stopOpacity={0.1} />
                  <stop offset="100%" stopColor="#0FEDBE" stopOpacity={0.01} />
                </linearGradient>
              </defs>
              <ReferenceArea y1={90} y2={100} fill="url(#evalSuccessBg)" />
              <CartesianGrid stroke="rgba(255,255,255,0.06)" />
              <XAxis
                dataKey="label"
                tick={{ fill: "#9ca3af", fontSize: 10 }}
                minTickGap={24}
                angle={-25}
                textAnchor="end"
                height={48}
                label={{
                  value: "Run Start (UTC)",
                  position: "insideBottom",
                  offset: -8,
                  fill: "#9ca3af",
                  fontSize: 10,
                }}
              />
              <YAxis
                domain={[90, 100]}
                tick={{ fill: "#9ca3af", fontSize: 10 }}
                label={{
                  value: "Run Success Rate (%)",
                  angle: -90,
                  position: "insideLeft",
                  fill: "#9ca3af",
                  dx: 12,
                  dy: 20,
                  fontSize: 10,
                }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#0b1220",
                  border: "1px solid #374151",
                  borderRadius: 10,
                }}
              />
              <Line
                dataKey="run_success_rate_pct"
                stroke="#0FEDBE"
                strokeWidth={2}
                dot={false}
                type="monotone"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </NotebookCell>

      <NotebookCell
        index={3}
        title="Latency Trend"
        cellKey="latencyChart"
        runState={runStates.latencyChart}
        onRun={runCell}
      >
        <div className="h-[240px] w-full sm:h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartRows} margin={{ top: 12, right: 12, left: 18, bottom: 42 }}>
              <defs>
                <linearGradient id="evalLatencyBg" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#0FEDBE" stopOpacity={0.08} />
                  <stop offset="100%" stopColor="#0FEDBE" stopOpacity={0.01} />
                </linearGradient>
              </defs>
              <ReferenceArea y1={120} y2={320} fill="url(#evalLatencyBg)" />
              <CartesianGrid stroke="rgba(255,255,255,0.06)" />
              <XAxis
                dataKey="label"
                tick={{ fill: "#9ca3af", fontSize: 10 }}
                minTickGap={24}
                angle={-25}
                textAnchor="end"
                height={48}
                label={{
                  value: "Run Start (UTC)",
                  position: "insideBottom",
                  offset: -8,
                  fill: "#9ca3af",
                  fontSize: 10,
                }}
              />
              <YAxis
                domain={[120, 320]}
                tick={{ fill: "#9ca3af", fontSize: 10 }}
                label={{
                  value: "Run Latency (sec)",
                  angle: -90,
                  position: "insideLeft",
                  fill: "#9ca3af",
                  dx: 12,
                  dy: 20,
                  fontSize: 10,
                }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#0b1220",
                  border: "1px solid #374151",
                  borderRadius: 10,
                }}
              />
              <ReferenceLine y={180} stroke="#22d3ee" strokeDasharray="5 5" />
              <ReferenceLine y={300} stroke="#FDD458" strokeDasharray="5 5" />
              <Line
                dataKey="run_latency_seconds"
                stroke="#5862FF"
                strokeWidth={2}
                dot={false}
                type="monotone"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="flex flex-wrap gap-3 text-xs text-gray-400">
          <p>Window: {summary.windowStartUtc} UTC + {summary.windowDays} days</p>
          <p>&lt;3m: {summary.lessThan3MinPct.toFixed(2)}%</p>
          <p>4-5m: {summary.between4And5MinPct.toFixed(2)}%</p>
          <p>&gt;5m runs: {summary.over5MinCount}</p>
        </div>
      </NotebookCell>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-gray-600 bg-gradient-to-b from-teal-400/5 to-black/30 px-3 py-2">
      <p className="text-[11px] uppercase tracking-wide text-gray-500">{label}</p>
      <p className="text-sm font-semibold text-gray-100">{value}</p>
    </div>
  );
}
