export interface SuggestedAlternative {
  alternative_type: string;
  alternative_command: string;
  estimated_token_savings_pct: number;
  explanation: string;
}

export interface AnalysisResult {
  developer_id: string;
  tokens_estimated: number;
  cost_usd: number;
  risk_level: "low" | "medium" | "high" | "unknown";
  suggested_alternative: SuggestedAlternative | null;
  tokens_saved: number;
  message?: string;
}

export interface RulesConfig {
  developer_id: string;
  budget_threshold_usd: number;
  action: "reroute" | "block";
  updated_at?: string;
}

export interface RecentCall {
  timestamp: string;
  tokens_estimated: number;
  cost_usd: number;
  risk_level: "low" | "medium" | "high" | "unknown";
  tokens_saved: number;
}

export interface MetricsResponse {
  developer_id: string;
  total_calls_analyzed: number;
  total_tokens_saved: number;
  total_cost_saved_usd: number;
  recent_calls: RecentCall[];
}
