import { useEffect, useState, useCallback } from "react";
import { fetchMetrics, isDemoMode } from "./api/client";
import SavingsCounter from "./components/SavingsCounter";
import AnalyzeTab from "./components/AnalyzeTab";
import RulesTab from "./components/RulesTab";
import MetricsTab from "./components/MetricsTab";

const PRICE_PER_1K_TOKENS = 0.000035;
const DEVELOPER_ID = "demo";

type Tab = "analyze" | "rules" | "metrics";

const tabs: { id: Tab; label: string }[] = [
  { id: "analyze", label: "Analyze" },
  { id: "rules", label: "Rules" },
  { id: "metrics", label: "Metrics" },
];

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>("analyze");
  const [totalTokensSaved, setTotalTokensSaved] = useState(0);
  const [totalCostSaved, setTotalCostSaved] = useState(0);
  const [demoMode, setDemoMode] = useState(false);

  // Sync the module-level isDemoMode flag into React state after API calls
  const syncDemoMode = useCallback(() => {
    setDemoMode(isDemoMode);
  }, []);

  // On mount: populate counters from metrics API
  useEffect(() => {
    fetchMetrics(DEVELOPER_ID)
      .then((data) => {
        setTotalTokensSaved(data.total_tokens_saved);
        setTotalCostSaved(data.total_cost_saved_usd);
        syncDemoMode();
      })
      .catch(() => {
        // Silently ignore; counters start at 0
      });
  }, [syncDemoMode]);

  const handleSavingsUpdate = (tokensSaved: number) => {
    setTotalTokensSaved((prev) => prev + tokensSaved);
    setTotalCostSaved(
      (prev) => prev + (tokensSaved * PRICE_PER_1K_TOKENS) / 1000
    );
    syncDemoMode();
  };

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-950/80 backdrop-blur sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <div className="flex items-center gap-2">
              <span className="text-xl font-bold text-blue-500">
                AgentGuard
              </span>
              <span className="text-xl font-bold text-white">.ai</span>
            </div>

            {/* Savings counter */}
            <SavingsCounter
              totalTokensSaved={totalTokensSaved}
              totalCostSaved={totalCostSaved}
            />
          </div>

          {/* Tab navigation */}
          <nav className="flex gap-0 -mb-px" role="tablist">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                role="tab"
                aria-selected={activeTab === tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-5 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? "border-blue-500 text-blue-400"
                    : "border-transparent text-gray-400 hover:text-gray-200 hover:border-gray-600"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === "analyze" && (
          <AnalyzeTab
            developerId={DEVELOPER_ID}
            onSavingsUpdate={handleSavingsUpdate}
          />
        )}
        {activeTab === "rules" && <RulesTab developerId={DEVELOPER_ID} />}
        {activeTab === "metrics" && (
          <MetricsTab
            developerId={DEVELOPER_ID}
            isActive={activeTab === "metrics"}
          />
        )}
      </main>
    </div>
  );
}
