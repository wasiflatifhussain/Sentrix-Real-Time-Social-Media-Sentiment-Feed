"use client";

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

export type SentimentChartPoint = {
  timeMs: number; // unix ms
  avg: number;
  volume: number;
};

// for hydration: fixed locale + timezone (no server/client mismatch)
const LOCALE = "en-HK";
const TZ = "Asia/Hong_Kong";

function formatTick(ms: number) {
  return new Date(ms).toLocaleString(LOCALE, {
    timeZone: TZ,
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    hour12: true,
  });
}

function formatTooltipLabel(ms: number) {
  return new Date(ms).toLocaleString(LOCALE, {
    timeZone: TZ,
    weekday: "short",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  });
}

export default function SentimentTimeSeriesChart({
  data,
}: {
  data: SentimentChartPoint[];
}) {
  // Older -> newer left-to-right
  const sorted = [...data].sort((a, b) => a.timeMs - b.timeMs);

  return (
    <ResponsiveContainer width="100%" height={460}>
      <LineChart
        data={sorted}
        margin={{
          top: 12,
          right: 12,
          left: 0,
          bottom: 92, // space for angled ticks (does NOT shrink chart height; container is taller)
        }}
      >
        {/* Zones */}
        <ReferenceArea y1={0.2} y2={1} fill="#10b981" fillOpacity={0.08} />
        <ReferenceArea y1={-0.2} y2={0.2} fill="#9ca3af" fillOpacity={0.05} />
        <ReferenceArea y1={-1} y2={-0.2} fill="#ef4444" fillOpacity={0.06} />

        <CartesianGrid stroke="rgba(255,255,255,0.05)" />

        {/* Real time axis: number + time scale */}
        <XAxis
          dataKey="timeMs"
          type="number"
          scale="time"
          domain={["dataMin", "dataMax"]}
          tickFormatter={(v) => formatTick(Number(v))}
          stroke="#9ca3af"
          tick={{ fontSize: 11, fill: "#9ca3af" }}
          angle={-35}
          textAnchor="end"
          height={5}
          tickMargin={14}
          minTickGap={16}
          interval="preserveStartEnd"
          allowDuplicatedCategory={false}
        />

        <YAxis
          domain={[-1, 1]}
          ticks={[-1, -0.5, 0, 0.5, 1]}
          tickFormatter={(v) => Number(v).toFixed(1)}
          stroke="#9ca3af"
        />

        <ReferenceLine y={0} stroke="#9ca3af" strokeOpacity={0.4} />

        <Tooltip
          contentStyle={{
            backgroundColor: "#0b1220",
            border: "1px solid #374151",
            borderRadius: 12,
          }}
          labelFormatter={(label) => formatTooltipLabel(Number(label))}
          formatter={(value: number, _k, p: any) => [
            Number(value).toFixed(3),
            `Avg Sentiment (posts: ${p?.payload?.volume ?? 0})`,
          ]}
        />

        <Line
          type="monotone"
          dataKey="avg"
          stroke="#0FEDBE"
          strokeWidth={2}
          dot={false}
          isAnimationActive={true}
          animationDuration={650}
          animationEasing="ease-out"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
