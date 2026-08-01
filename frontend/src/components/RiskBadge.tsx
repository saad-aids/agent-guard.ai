type RiskLevel = "low" | "medium" | "high" | "unknown";

interface RiskBadgeProps {
  riskLevel: RiskLevel;
}

const riskStyles: Record<RiskLevel, { bg: string; label: string }> = {
  low: { bg: "bg-green-500/20 text-green-400", label: "Low" },
  medium: { bg: "bg-yellow-500/20 text-yellow-400", label: "Medium" },
  high: { bg: "bg-red-500/20 text-red-400", label: "High" },
  unknown: { bg: "bg-gray-500/20 text-gray-400", label: "Unknown" },
};

export default function RiskBadge({ riskLevel }: RiskBadgeProps) {
  const { bg, label } = riskStyles[riskLevel] ?? riskStyles.unknown;
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${bg}`}
    >
      {label}
    </span>
  );
}
