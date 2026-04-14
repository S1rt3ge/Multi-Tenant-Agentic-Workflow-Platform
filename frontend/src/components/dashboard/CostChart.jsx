import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';

/**
 * CostChart — line chart showing daily cost over time.
 *
 * Props:
 *   data: [{ day: "2026-04-14", daily_cost: 0.05, executions_count: 2 }, ...]
 *   budgetLine: number | null — monthly budget in $ to show as horizontal reference line
 *   days: number — currently selected number of days
 *   onChangeDays: (days) => void
 */
export default function CostChart({ data, budgetLine, days, onChangeDays }) {
  const dayOptions = [7, 14, 30, 60, 90];

  const formatDay = (day) => {
    const d = new Date(day + 'T00:00:00');
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload || !payload.length) return null;
    const item = payload[0].payload;
    return (
      <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3 text-sm">
        <p className="font-medium text-gray-900 mb-1">{formatDay(label)}</p>
        <p className="text-gray-600">
          Cost: <span className="font-medium text-gray-900">${item.daily_cost.toFixed(4)}</span>
        </p>
        <p className="text-gray-600">
          Executions: <span className="font-medium text-gray-900">{item.executions_count}</span>
        </p>
      </div>
    );
  };

  const hasData = data.some((d) => d.daily_cost > 0);

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-900">Cost Timeline</h3>
        <div className="flex gap-1">
          {dayOptions.map((d) => (
            <button
              key={d}
              onClick={() => onChangeDays(d)}
              className={`px-2.5 py-1 text-xs rounded-md transition-colors ${
                days === d
                  ? 'bg-blue-100 text-blue-700 font-medium'
                  : 'text-gray-500 hover:bg-gray-100'
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {!hasData ? (
        <div className="flex items-center justify-center h-64 text-sm text-gray-400">
          No executions in this period
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis
              dataKey="day"
              tickFormatter={formatDay}
              tick={{ fontSize: 11, fill: '#9ca3af' }}
              axisLine={{ stroke: '#e5e7eb' }}
              tickLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              tickFormatter={(v) => `$${v}`}
              tick={{ fontSize: 11, fill: '#9ca3af' }}
              axisLine={false}
              tickLine={false}
              width={50}
            />
            <Tooltip content={<CustomTooltip />} />
            <Line
              type="monotone"
              dataKey="daily_cost"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: '#3b82f6' }}
            />
            {budgetLine && budgetLine > 0 && (
              <ReferenceLine
                y={budgetLine}
                stroke="#ef4444"
                strokeDasharray="6 4"
                strokeWidth={1.5}
                label={{
                  value: `Budget $${budgetLine}`,
                  position: 'right',
                  fill: '#ef4444',
                  fontSize: 11,
                }}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
