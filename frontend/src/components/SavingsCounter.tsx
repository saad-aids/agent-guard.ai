interface SavingsCounterProps {
  totalTokensSaved: number;
  totalCostSaved: number;
}

export default function SavingsCounter({
  totalTokensSaved,
  totalCostSaved,
}: SavingsCounterProps) {
  return (
    <div className="flex items-center gap-6">
      <div className="text-center">
        <p className="text-xs text-gray-400 uppercase tracking-wide">
          Tokens Saved
        </p>
        <p className="text-lg font-semibold text-blue-400">
          {totalTokensSaved.toLocaleString()}
        </p>
      </div>
      <div className="text-center">
        <p className="text-xs text-gray-400 uppercase tracking-wide">
          $ Saved
        </p>
        <p className="text-lg font-semibold text-blue-400">
          ${totalCostSaved.toFixed(4)}
        </p>
      </div>
    </div>
  );
}
