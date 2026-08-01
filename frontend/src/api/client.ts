import type { AnalysisResult, RulesConfig, MetricsResponse } from "../types";

const API_BASE = import.meta.env.VITE_API_BASE_URL as string;
const API_KEY = import.meta.env.VITE_API_KEY as string;

const headers = {
  "Content-Type": "application/json",
  "X-API-Key": API_KEY,
};

// ---------------------------------------------------------------------------
// Demo-mode flag
// Set to true whenever a mock response is returned in place of a real one.
// Components can import this to show a "Demo Mode" badge.
// ---------------------------------------------------------------------------

export let isDemoMode = false;

function setDemoMode(active: boolean) {
  isDemoMode = active;
}

// ---------------------------------------------------------------------------
// Mock data — used as fallback when the real backend is unreachable
// ---------------------------------------------------------------------------

function mockAnalyzeResult(developerId: string): AnalysisResult {
  return {
    developer_id: developerId,
    tokens_estimated: 47000,
    cost_usd: 1.645,
    risk_level: "high",
    suggested_alternative: {
      alternative_type: "cli_command",
      alternative_command:
        "aws s3 ls s3://my-bucket --recursive --human-readable | awk '{print $3, $5}'",
      estimated_token_savings_pct: 94,
      explanation:
        "Direct S3 CLI listing replaces a 47 k-token agent traversal that reads every object individually.",
    },
    tokens_saved: 44000,
  };
}

function mockMetricsResult(developerId: string): MetricsResponse {
  const now = Date.now();
  const hour = 3_600_000;
  return {
    developer_id: developerId,
    total_calls_analyzed: 12,
    total_tokens_saved: 128500,
    total_cost_saved_usd: 4.50,
    recent_calls: [
      {
        timestamp: new Date(now - hour * 0.5).toISOString(),
        tokens_estimated: 47000,
        cost_usd: 1.645,
        risk_level: "high",
        tokens_saved: 44000,
      },
      {
        timestamp: new Date(now - hour * 1.2).toISOString(),
        tokens_estimated: 12400,
        cost_usd: 0.434,
        risk_level: "high",
        tokens_saved: 11600,
      },
      {
        timestamp: new Date(now - hour * 2.7).toISOString(),
        tokens_estimated: 3800,
        cost_usd: 0.133,
        risk_level: "medium",
        tokens_saved: 0,
      },
      {
        timestamp: new Date(now - hour * 4.1).toISOString(),
        tokens_estimated: 800,
        cost_usd: 0.028,
        risk_level: "low",
        tokens_saved: 0,
      },
      {
        timestamp: new Date(now - hour * 5.9).toISOString(),
        tokens_estimated: 31200,
        cost_usd: 1.092,
        risk_level: "high",
        tokens_saved: 29300,
      },
    ],
  };
}

function mockSaveRules(
  config: Omit<RulesConfig, "updated_at">
): RulesConfig {
  return {
    ...config,
    updated_at: new Date().toISOString(),
  };
}

// ---------------------------------------------------------------------------
// API functions — real call first, mock fallback on any failure
// ---------------------------------------------------------------------------

export async function analyzePayload(
  developerId: string,
  payload: string
): Promise<AnalysisResult> {
  try {
    const response = await fetch(`${API_BASE}/v1/analyze-log`, {
      method: "POST",
      headers,
      body: JSON.stringify({ developer_id: developerId, payload }),
    });
    const data = await response.json() as AnalysisResult;
    setDemoMode(false);
    return data;
  } catch {
    setDemoMode(true);
    return mockAnalyzeResult(developerId);
  }
}

export async function saveRules(
  config: Omit<RulesConfig, "updated_at">
): Promise<RulesConfig> {
  try {
    const response = await fetch(`${API_BASE}/v1/rules`, {
      method: "POST",
      headers,
      body: JSON.stringify(config),
    });
    const data = await response.json() as RulesConfig;
    setDemoMode(false);
    return data;
  } catch {
    setDemoMode(true);
    return mockSaveRules(config);
  }
}

export async function fetchMetrics(
  developerId: string
): Promise<MetricsResponse> {
  try {
    const response = await fetch(
      `${API_BASE}/v1/metrics/dashboard?developer_id=${encodeURIComponent(developerId)}`,
      {
        method: "GET",
        headers,
      }
    );
    const data = await response.json() as MetricsResponse;
    setDemoMode(false);
    return data;
  } catch {
    setDemoMode(true);
    return mockMetricsResult(developerId);
  }
}
