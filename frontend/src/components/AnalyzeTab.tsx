import { useState } from "react";
import type { AnalysisResult } from "../types";
import { analyzePayload } from "../api/client";
import RiskBadge from "./RiskBadge";

interface AnalyzeTabProps {
  developerId: string;
  onSavingsUpdate: (tokensSaved: number) => void;
}

export default function AnalyzeTab({
  developerId,
  onSavingsUpdate,
}: AnalyzeTabProps) {
  const [payloadText, setPayloadText] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleAnalyze = async () => {
    if (!payloadText.trim()) return;

    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await analyzePayload(developerId, payloadText);
      setResult(data);
      if (data.tokens_saved > 0) {
        onSavingsUpdate(data.tokens_saved);
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "An unexpected error occurred."
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Payload textarea */}
      <div>
        <label
          htmlFor="payload-input"
          className="block text-sm font-medium text-gray-300 mb-2"
        >
          Paste your tool-call payload
        </label>
        <textarea
          id="payload-input"
          value={payloadText}
          onChange={(e) => setPayloadText(e.target.value)}
          rows={8}
          placeholder="Paste your AI agent tool-call payload here..."
          className="w-full bg-gray-900 border border-gray-700 rounded-lg p-3 text-gray-100 placeholder-gray-500 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-y"
        />
      </div>

      {/* Analyze button */}
      <button
        onClick={handleAnalyze}
        disabled={isLoading || !payloadText.trim()}
        className="flex items-center gap-2 px-6 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-600/40 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-colors"
      >
        {isLoading && (
          <svg
            className="animate-spin h-4 w-4 text-white"
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
        )}
        {isLoading ? "Analyzing…" : "Analyze"}
      </button>

      {/* Error banner */}
      {error && (
        <div
          role="alert"
          className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-4 text-sm"
        >
          {error}
        </div>
      )}

      {/* Result card */}
      {result && (
        <div className="bg-gray-900 border border-gray-700 rounded-lg p-5 space-y-4">
          {/* Message banner (fallback notice) */}
          {result.message && (
            <div className="bg-yellow-500/10 border border-yellow-500/30 text-yellow-400 rounded-lg p-3 text-sm">
              {result.message}
            </div>
          )}

          {/* Risk + cost row */}
          <div className="flex flex-wrap items-center gap-4">
            <div>
              <p className="text-xs text-gray-400 mb-1">Risk Level</p>
              <RiskBadge riskLevel={result.risk_level} />
            </div>
            <div>
              <p className="text-xs text-gray-400 mb-1">Tokens Estimated</p>
              <p className="text-white font-mono font-semibold">
                {result.tokens_estimated.toLocaleString()}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-400 mb-1">Cost (USD)</p>
              <p className="text-white font-mono font-semibold">
                ${result.cost_usd.toFixed(6)}
              </p>
            </div>
            {result.tokens_saved > 0 && (
              <div>
                <p className="text-xs text-gray-400 mb-1">Tokens Saved</p>
                <p className="text-green-400 font-mono font-semibold">
                  {result.tokens_saved.toLocaleString()}
                </p>
              </div>
            )}
          </div>

          {/* Alternative block */}
          {result.suggested_alternative && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-gray-300">
                  Suggested Alternative
                </p>
                <span className="text-xs text-gray-500 capitalize">
                  {result.suggested_alternative.alternative_type.replace(
                    "_",
                    " "
                  )}
                  {" · "}
                  {result.suggested_alternative.estimated_token_savings_pct}%
                  savings
                </span>
              </div>
              <pre className="bg-gray-800 font-mono text-sm p-4 rounded-lg text-green-300 overflow-x-auto whitespace-pre-wrap break-words">
                {result.suggested_alternative.alternative_command}
              </pre>
              <p className="text-sm text-gray-400">
                {result.suggested_alternative.explanation}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
