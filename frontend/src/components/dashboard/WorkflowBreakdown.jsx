import { ArrowDownRight } from 'lucide-react';

/**
 * WorkflowBreakdown — table showing per-workflow analytics.
 *
 * Props:
 *   data: [{ workflow_id, workflow_name, runs, cost, avg_duration_sec, cost_percentage }, ...]
 */
export default function WorkflowBreakdown({ data }) {
  const formatDuration = (sec) => {
    if (sec === null || sec === undefined) return '-';
    if (sec < 60) return `${sec.toFixed(1)}s`;
    const min = Math.floor(sec / 60);
    const s = Math.round(sec % 60);
    return `${min}m ${s}s`;
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="text-sm font-semibold text-gray-900 mb-4">
        Workflow Breakdown
      </h3>

      {data.length === 0 ? (
        <div className="flex items-center justify-center py-12 text-sm text-gray-400">
          No workflow data for this period
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="text-left py-2.5 px-3 font-medium text-gray-500 text-xs uppercase tracking-wider">
                  Workflow
                </th>
                <th className="text-right py-2.5 px-3 font-medium text-gray-500 text-xs uppercase tracking-wider">
                  Runs
                </th>
                <th className="text-right py-2.5 px-3 font-medium text-gray-500 text-xs uppercase tracking-wider">
                  Cost
                </th>
                <th className="text-right py-2.5 px-3 font-medium text-gray-500 text-xs uppercase tracking-wider">
                  Avg Duration
                </th>
                <th className="text-left py-2.5 px-3 font-medium text-gray-500 text-xs uppercase tracking-wider w-40">
                  % of Total
                </th>
              </tr>
            </thead>
            <tbody>
              {data.map((row) => (
                <tr
                  key={row.workflow_id}
                  className="border-b border-gray-50 hover:bg-gray-50 transition-colors"
                >
                  <td className="py-3 px-3">
                    <span className="font-medium text-gray-900">
                      {row.workflow_name}
                    </span>
                  </td>
                  <td className="py-3 px-3 text-right text-gray-700">
                    {row.runs.toLocaleString()}
                  </td>
                  <td className="py-3 px-3 text-right text-gray-700">
                    ${row.cost.toFixed(4)}
                  </td>
                  <td className="py-3 px-3 text-right text-gray-700">
                    {formatDuration(row.avg_duration_sec)}
                  </td>
                  <td className="py-3 px-3">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-blue-500 rounded-full transition-all"
                          style={{ width: `${row.cost_percentage}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-500 w-12 text-right">
                        {row.cost_percentage.toFixed(1)}%
                      </span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
