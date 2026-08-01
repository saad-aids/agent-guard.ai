import { useEffect, useState } from "react";
import type { MetricsResponse, RecentCall } from "../types";
import { fetchMetrics } from "../api/client";
import RiskBadge from "./RiskBadge";

interface MetricsTabProps {
  developerId: string;
  isActive: boolean;
}

// Inline SVG bar chart — no external charting library needed
function TokensSavedChart({ calls }: { calls: RecentCall[] }) {
  const chartWidth = 600;
  const chartHeight = 160;
  const paddingLeft = 48;
  const paddingRight = 16;
  const paddingTop = 12;
  const paddingBottom = 32;

  const barAreaWidth = chartWidth - paddingLeft - paddingRight;
  const barAreaHeight = chartHeight - paddingTop - paddingBottom;

  const relevant = calls.slice().reverse(); // oldest → newest for left-to-right
  const maxSaved = Math.max(...relevant.map((c) => c.tokens_saved), 1);

  if (relevant.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-gray-500 text-sm">
        No data yet
      </div>
    );
  }

  const barCount = relevant.length;
  const gap = Math.max(2, Math.floor(barAreaWidth / barCount / 5));
  const barWidth = Math.max(4, Math.floor((barAreaWidth - gap * (barCount - 1)) / barCount));

  return (
    <svg
      viewBox={`0 0 ${chartWidth} ${chartHeight}`}
      className="w-full"
      role="img"
      aria-label="Tokens saved per call bar chart"
    >
      {/* Y-axis label */}
      <text
        x={paddingLeft - 6}
        y={paddingTop}
        textAnchor="end"
        className="fill-gray-500"
        fontSize={10}
      >
        {maxSaved.toLocaleString()}
      </text>
      <text
        x={paddingLeft - 6}
        y={paddingTop + barAreaHeight}
        textAnchor="end"
        className="fill-gray-500"
        fontSize={10}
      >
        0
      </text>

      {/* Baseline */}
      <line
        x1={paddingLeft}
        y1={paddingTop + barAreaHeight}
        x2={chartWidth - paddingRight}
        y2={paddingTop + barAreaHeight}
        stroke="#374151"
        strokeWidth={1}
      />

      {/* Bars */}
      {relevant.map((call, i) => {
        const barHeight = Math.max(
          2,
          (call.tokens_saved / maxSaved) * barAreaHeight
        );
        const x = paddingLeft + i * (barWidth + gap);
        const y = paddingTop + barAreaHeight - barHeight;

        return (
          <g key={i}>
            <rect
              x={x}
              y={y}
              width={barWidth}
              height={barHeight}
              fill="#3B82F6"
              rx={2}
            >
              <title>{`${call.tokens_saved.toLocaleString()} tokens saved`}</title>
            </rect>
          </g>
        );
      })}
    </svg>
  );
}

function formatTimestamp(ts: string): string {
  try {
    return new Date(ts).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return ts;
  }
}

export default function MetricsTab({ developerId, isActive }: MetricsTabProps) {
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isActive) return;

    let cancelled = false;
    setIsLoading(true);
    setError(null);

    fetchMetrics(developerId)
      .then((data) => {
        if (!cancelled) setMetrics(data);
      })
      .catch((err) => {
        if (!cancelled)
          setError(
            err instanceof Error ? err.message : "Failed to load metrics."
          );
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [isActive, developerId]);

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-gray-400 text-sm py-8">
        <svg
          className="animate-spin h-4 w-4"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
          />
        </svg>
        Loading metrics…
      </div>
    );
  }

  if (error) {
    return (
      <div
        role="alert"
        className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-4 text-sm"
      >
        {error}
      </div>
    );
  }

  const calls = metrics?.recent_calls ?? [];

  return (
    <div className="space-y-8">
      {/* Summary stats */}
      {metrics && (
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 text-center">
            <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">
              Total Calls
            </p>
            <p className="text-2xl font-bold text-white">
              {metrics.total_calls_analyzed.toLocaleString()}
            </p>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 text-center">
            <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">
              Tokens Saved
            </p>
            <p className="text-2xl font-bold text-blue-400">
              {metrics.total_tokens_saved.toLocaleString()}
            </p>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 text-center">
            <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">
              Cost Saved
            </p>
            <p className="text-2xl font-bold text-green-400">
              ${metrics.total_cost_saved_usd.toFixed(4)}
            </p>
          </div>
        </div>
      )}

      {/* Chart */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <h3 className="text-sm font-medium text-gray-300 mb-3">
          Tokens Saved per Call
        </h3>
        <TokensSavedChart calls={calls} />
      </div>

      {/* Table */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-800">
          <h3 className="text-sm font-medium text-gray-300">Recent Calls</h3>
        </div>
        {calls.length === 0 ? (
          <div className="text-center py-10 text-gray-500 text-sm">
            No calls recorded yet.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-left">
                  <th className="px-4 py-3 text-xs font-medium text-gray-400 uppercase tracking-wide">
                    Timestamp
                  </th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-400 uppercase tracking-wide text-right">
                    Tokens Est.
                  </th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-400 uppercase tracking-wide text-right">
                    Cost (USD)
                  </th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-400 uppercase tracking-wide">
                    Risk
                  </th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-400 uppercase tracking-wide text-right">
                    Tokens Saved
                  </th>
                </tr>
              </thead>
              <tbody>
                {calls.map((call, i) => (
                  <tr
                    key={i}
                    className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors"
                  >
                    <td className="px-4 py-3 text-gray-300 font-mono text-xs">
                      {formatTimestamp(call.timestamp)}
                    </td>
                    <td className="px-4 py-3 text-gray-300 font-mono text-right">
                      {call.tokens_estimated.toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-gray-300 font-mono text-right">
                      ${call.cost_usd.toFixed(6)}
                    </td>
                    <td className="px-4 py-3">
                      <RiskBadge riskLevel={call.risk_level} />
                    </td>
                    <td className="px-4 py-3 text-right">
                      {call.tokens_saved > 0 ? (
                        <span className="text-green-400 font-mono">
                          {call.tokens_saved.toLocaleString()}
                        </span>
                      ) : (
                        <span className="text-gray-600 font-mono">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
