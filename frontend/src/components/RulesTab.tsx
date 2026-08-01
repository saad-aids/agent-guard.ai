import { useState } from "react";
import type { RulesConfig } from "../types";
import { saveRules } from "../api/client";

interface RulesTabProps {
  developerId: string;
}

type SaveStatus = "idle" | "success" | "error";

export default function RulesTab({ developerId }: RulesTabProps) {
  const [budgetThreshold, setBudgetThreshold] = useState<string>("0.01");
  const [action, setAction] = useState<"reroute" | "block">("reroute");
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleSave = async () => {
    setValidationError(null);
    setSaveStatus("idle");
    setSaveError(null);

    const threshold = parseFloat(budgetThreshold);
    if (isNaN(threshold) || threshold <= 0) {
      setValidationError(
        "Budget threshold must be a positive number greater than 0."
      );
      return;
    }

    setIsSaving(true);
    try {
      await saveRules({
        developer_id: developerId,
        budget_threshold_usd: threshold,
        action,
      } as Omit<RulesConfig, "updated_at">);
      setSaveStatus("success");
    } catch (err) {
      setSaveStatus("error");
      setSaveError(
        err instanceof Error ? err.message : "Failed to save rules. Please try again."
      );
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="max-w-lg space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-white mb-1">
          Budget &amp; Action Rules
        </h2>
        <p className="text-sm text-gray-400">
          Set your per-call cost threshold and choose what happens when it's
          exceeded.
        </p>
      </div>

      {/* Budget Threshold Input */}
      <div>
        <label
          htmlFor="budget-threshold"
          className="block text-sm font-medium text-gray-300 mb-2"
        >
          Budget Threshold (USD)
        </label>
        <div className="relative">
          <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-gray-400 pointer-events-none">
            $
          </span>
          <input
            id="budget-threshold"
            type="number"
            min="0.000001"
            step="0.001"
            value={budgetThreshold}
            onChange={(e) => {
              setBudgetThreshold(e.target.value);
              setValidationError(null);
              setSaveStatus("idle");
            }}
            className="w-full bg-gray-900 border border-gray-700 rounded-lg pl-7 pr-3 py-2.5 text-white font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            placeholder="0.01"
          />
        </div>
        {validationError && (
          <p className="mt-1.5 text-xs text-red-400">{validationError}</p>
        )}
      </div>

      {/* Action Toggle */}
      <div>
        <p className="block text-sm font-medium text-gray-300 mb-3">
          Action when threshold exceeded
        </p>
        <div className="flex gap-3">
          <button
            onClick={() => setAction("reroute")}
            className={`flex-1 py-2.5 px-4 rounded-lg border text-sm font-medium transition-colors ${
              action === "reroute"
                ? "bg-blue-600/20 border-blue-500 text-blue-400"
                : "bg-gray-900 border-gray-700 text-gray-400 hover:border-gray-500"
            }`}
          >
            Reroute
          </button>
          <button
            onClick={() => setAction("block")}
            className={`flex-1 py-2.5 px-4 rounded-lg border text-sm font-medium transition-colors ${
              action === "block"
                ? "bg-red-600/20 border-red-500 text-red-400"
                : "bg-gray-900 border-gray-700 text-gray-400 hover:border-gray-500"
            }`}
          >
            Block
          </button>
        </div>
        <p className="mt-2 text-xs text-gray-500">
          {action === "reroute"
            ? "The call will be flagged and a cheaper alternative will be suggested."
            : "The call will be blocked and must be replaced before execution."}
        </p>
      </div>

      {/* Save button */}
      <button
        onClick={handleSave}
        disabled={isSaving}
        className="flex items-center gap-2 px-6 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-600/40 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-colors"
      >
        {isSaving && (
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
        )}
        {isSaving ? "Saving…" : "Save Rules"}
      </button>

      {/* Success banner */}
      {saveStatus === "success" && (
        <div
          role="status"
          className="bg-green-500/10 border border-green-500/30 text-green-400 rounded-lg p-4 text-sm"
        >
          Rules saved successfully.
        </div>
      )}

      {/* Error banner */}
      {saveStatus === "error" && saveError && (
        <div
          role="alert"
          className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-4 text-sm"
        >
          {saveError}
        </div>
      )}
    </div>
  );
}
