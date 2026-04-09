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

import filterBViewRaw from "@/data/evaluation/filter_b_frontend_view.json";
import { Button } from "@/components/ui/button";

type FilterBChartRow = {
  run_started_at_utc: string;
  label: string;
  decision_correctness_pct: number;
  false_positive_rate_pct: number;
  false_negative_rate_pct: number;
  throughput_events_per_sec: number;
};

type FilterBSummary = {
  runsObserved: number;
  runsExpected: number;
  coveragePct: number;
  avgCorrectnessPct: number;
  weightedCorrectnessPct: number;
  fpRatePct: number;
  fnRatePct: number;
  throughputMean: number;
};

type FilterBView = {
  summary: FilterBSummary;
  charts: FilterBChartRow[];
};

type CellKey = "summary" | "correctnessChart" | "errorThroughputChart";

const filterBView = filterBViewRaw as FilterBView;

const CODE_SNIPPETS: Record<CellKey, string> = {
  summary: `# Cell [1] - Filter-B correctness summary
precomputed = pd.read_json("frontend/data/evaluation/filter_b_frontend_view.json")
summary = precomputed["summary"]
display(summary)`,
  correctnessChart: `# Cell [2] - Correctness trend
plot_df = precomputed["charts"]

fig, ax = plt.subplots(figsize=(11, 4))
ax.plot(plot_df["run_started_at_utc"], plot_df["decision_correctness_pct"], color="#0FEDBE", linewidth=2)
ax.axhline(82, linestyle="--", color="#22d3ee")
ax.set_title("Filter-B Decision Correctness (%)")
ax.set_ylabel("Correctness %")
ax.set_xlabel("Run Start (UTC)")
ax.grid(alpha=0.15)`,
  errorThroughputChart: `# Cell [3] - Error profile + throughput
plot_df = precomputed["charts"]

fig, ax = plt.subplots(figsize=(11, 4))
ax.plot(plot_df["run_started_at_utc"], plot_df["false_positive_rate_pct"], label="FP rate")
ax.plot(plot_df["run_started_at_utc"], plot_df["false_negative_rate_pct"], label="FN rate")
ax2 = ax.twinx()
ax2.plot(plot_df["run_started_at_utc"], plot_df["throughput_events_per_sec"], color="#5862FF")
ax.legend()
ax.set_title("Filter-B Error Rates and Throughput")
ax.set_xlabel("Run Start (UTC)")`,
};

const PYTHON_KEYWORDS = new Set([
  "display",
  "plot",
  "read_json",
  "axhline",
  "set_title",
  "set_ylabel",
  "set_xlabel",
  "legend",
  "twinx",
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
        <Button
          onClick={() => onRun(cellKey)}
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
    } else if (full === "df" || full === "window" || full === "summary" || full === "ax" || full === "ax2") {
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

export default function FilterBPerformanceNotebook() {
  const [runStates, setRunStates] = useState<Record<CellKey, "idle" | "running" | "done">>({
    summary: "idle",
    correctnessChart: "idle",
    errorThroughputChart: "idle",
  });

  const chartRows = filterBView.charts;
  const summary = filterBView.summary;

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
        title="Filter-B KPI Table"
        cellKey="summary"
        runState={runStates.summary}
        onRun={runCell}
      >
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
          <MetricCard label="Runs" value={`${summary.runsObserved}/${summary.runsExpected}`} />
          <MetricCard label="Coverage" value={`${summary.coveragePct.toFixed(2)}%`} />
          <MetricCard label="Avg Correct" value={`${summary.avgCorrectnessPct.toFixed(2)}%`} />
          <MetricCard
            label="Weighted Correct"
            value={`${summary.weightedCorrectnessPct.toFixed(2)}%`}
          />
          <MetricCard label="FP Rate" value={`${summary.fpRatePct.toFixed(2)}%`} />
          <MetricCard label="FN Rate" value={`${summary.fnRatePct.toFixed(2)}%`} />
        </div>
      </NotebookCell>

      <NotebookCell
        index={2}
        title="Decision Correctness Trend"
        cellKey="correctnessChart"
        runState={runStates.correctnessChart}
        onRun={runCell}
      >
        <div className="h-[240px] w-full sm:h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartRows} margin={{ top: 12, right: 12, left: 18, bottom: 42 }}>
              <ReferenceArea y1={80} y2={84} fill="#0FEDBE" fillOpacity={0.08} />
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
                domain={[74, 90]}
                tick={{ fill: "#9ca3af", fontSize: 10 }}
                label={{
                  value: "Decision Correctness (%)",
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
              <ReferenceLine y={82} stroke="#22d3ee" strokeDasharray="5 5" />
              <Line dataKey="decision_correctness_pct" stroke="#0FEDBE" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </NotebookCell>

      <NotebookCell
        index={3}
        title="Error Rates and Throughput"
        cellKey="errorThroughputChart"
        runState={runStates.errorThroughputChart}
        onRun={runCell}
      >
        <div className="h-[240px] w-full sm:h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartRows} margin={{ top: 12, right: 12, left: 18, bottom: 42 }}>
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
                yAxisId="left"
                tick={{ fill: "#9ca3af", fontSize: 10 }}
                label={{
                  value: "Error Rate (%)",
                  angle: -90,
                  position: "insideLeft",
                  fill: "#9ca3af",
                  dx: 12,
                  dy: 20,
                  fontSize: 10,
                }}
              />
              <YAxis
                yAxisId="right"
                orientation="right"
                tick={{ fill: "#9ca3af", fontSize: 10 }}
                label={{
                  value: "Throughput (events/sec)",
                  angle: 90,
                  position: "insideRight",
                  fill: "#9ca3af",
                  dx: -10,
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
              <Line yAxisId="left" dataKey="false_positive_rate_pct" stroke="#FDD458" strokeWidth={2} dot={false} />
              <Line yAxisId="left" dataKey="false_negative_rate_pct" stroke="#FF8243" strokeWidth={2} dot={false} />
              <Line
                yAxisId="right"
                dataKey="throughput_events_per_sec"
                stroke="#5862FF"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="flex flex-wrap gap-3 text-xs text-gray-400">
          <p>Target correctness: ~82%</p>
          <p>Weighted correctness: {summary.weightedCorrectnessPct.toFixed(2)}%</p>
          <p>Mean throughput: {summary.throughputMean.toFixed(2)} eps</p>
        </div>
      </NotebookCell>
    </div>
  );
}
