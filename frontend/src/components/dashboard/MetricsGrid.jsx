import { Activity, CheckCircle, Coins, Zap } from 'lucide-react';

/**
 * MetricsGrid — 4 KPI cards in a row.
 * Cards: Total Executions, Success Rate, Tokens Used, Total Cost.
 *
 * Props:
 *   overview: { total_executions, successful, failed, tokens_used, total_cost, success_rate }
 *   tenant: { monthly_token_budget, ... } (optional, for budget display)
 */
export default function MetricsGrid({ overview, tenant }) {
  if (!overview) return null;

  const {
    total_executions,
    successful,
    failed,
    tokens_used,
    total_cost,
    success_rate,
  } = overview;

  const budget = tenant?.monthly_token_budget || 0;
  const budgetPercent = budget > 0 ? Math.min((tokens_used / budget) * 100, 100) : 0;

  const cards = [
    {
      title: 'Total Executions',
      value: total_executions.toLocaleString(),
      subtitle: `${successful} succeeded, ${failed} failed`,
      icon: Activity,
      color: 'blue',
    },
    {
      title: 'Success Rate',
      value: success_rate !== null ? `${success_rate}%` : 'N/A',
      subtitle:
        success_rate !== null
          ? success_rate >= 90
            ? 'Excellent'
            : success_rate >= 70
            ? 'Good'
            : 'Needs attention'
          : 'No executions yet',
      icon: CheckCircle,
      color: success_rate === null ? 'gray' : success_rate >= 70 ? 'green' : 'red',
      progress: success_rate,
    },
    {
      title: 'Tokens Used',
      value: tokens_used.toLocaleString(),
      subtitle: budget > 0 ? `${budgetPercent.toFixed(1)}% of budget (${budget.toLocaleString()})` : 'No budget limit',
      icon: Zap,
      color: budgetPercent > 90 ? 'red' : budgetPercent > 70 ? 'yellow' : 'blue',
      progress: budget > 0 ? budgetPercent : null,
    },
    {
      title: 'Total Cost',
      value: `$${total_cost.toFixed(2)}`,
      subtitle: total_executions > 0 ? `$${(total_cost / total_executions).toFixed(4)} avg per run` : 'No cost data',
      icon: Coins,
      color: 'purple',
    },
  ];

  const colorClasses = {
    blue: { bg: 'bg-blue-50', text: 'text-blue-600', progress: 'bg-blue-500' },
    green: { bg: 'bg-green-50', text: 'text-green-600', progress: 'bg-green-500' },
    red: { bg: 'bg-red-50', text: 'text-red-600', progress: 'bg-red-500' },
    yellow: { bg: 'bg-yellow-50', text: 'text-yellow-600', progress: 'bg-yellow-500' },
    purple: { bg: 'bg-purple-50', text: 'text-purple-600', progress: 'bg-purple-500' },
    gray: { bg: 'bg-gray-50', text: 'text-gray-400', progress: 'bg-gray-400' },
  };

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((card) => {
        const colors = colorClasses[card.color] || colorClasses.blue;
        const Icon = card.icon;

        return (
          <div
            key={card.title}
            className="bg-white rounded-xl border border-gray-200 p-5"
          >
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium text-gray-500">
                {card.title}
              </span>
              <div className={`p-2 rounded-lg ${colors.bg}`}>
                <Icon className={`h-4 w-4 ${colors.text}`} />
              </div>
            </div>

            <p className="text-2xl font-bold text-gray-900 mb-1">
              {card.value}
            </p>
            <p className="text-xs text-gray-500">{card.subtitle}</p>

            {card.progress !== null && card.progress !== undefined && (
              <div className="mt-3">
                <div className="w-full h-1.5 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${colors.progress}`}
                    style={{ width: `${Math.min(card.progress, 100)}%` }}
                  />
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
