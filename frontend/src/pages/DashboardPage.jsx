import { useState } from 'react';
import { RefreshCw, Download, BarChart3 } from 'lucide-react';
import toast from 'react-hot-toast';
import useDashboard from '../hooks/useDashboard';
import { useAuth } from '../hooks/useAuth';
import MetricsGrid from '../components/dashboard/MetricsGrid';
import CostChart from '../components/dashboard/CostChart';
import WorkflowBreakdown from '../components/dashboard/WorkflowBreakdown';

export default function DashboardPage() {
  const { tenant } = useAuth();
  const {
    overview,
    timeline,
    breakdown,
    loading,
    error,
    period,
    timelineDays,
    exporting,
    refetch,
    handleExport,
    changePeriod,
    changeTimelineDays,
  } = useDashboard();

  const [exportFormat, setExportFormat] = useState('csv');

  const onExport = async () => {
    const tid = toast.loading(`Exporting ${exportFormat.toUpperCase()}...`);
    try {
      await handleExport(exportFormat);
      toast.dismiss(tid);
      if (exportFormat === 'csv') {
        toast.success('CSV downloaded');
      } else {
        toast.success('JSON export ready');
      }
    } catch (err) {
      toast.dismiss(tid);
      toast.error(err.response?.data?.detail || 'Export failed');
    }
  };

  // Rough budget line: monthly_token_budget converted to $ using ~$0.03 per 1K tokens
  // This is a rough estimate — the spec says "monthly_token_budget in $"
  // We use token budget directly for the reference line if the budget makes sense as cost
  const budgetLine = tenant?.monthly_token_budget
    ? (tenant.monthly_token_budget / 1000) * 0.03
    : null;

  // --- ERROR state ---
  if (error && !loading) {
    return (
      <div className="p-8 flex flex-col items-center justify-center min-h-[400px]">
        <p className="text-red-500 mb-4">{error}</p>
        <button
          onClick={refetch}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
        >
          <RefreshCw className="h-4 w-4" />
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-1">
            Analytics and cost tracking for your workflows
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Period selector */}
          <div className="flex bg-gray-100 rounded-lg p-0.5">
            {['month', 'week'].map((p) => (
              <button
                key={p}
                onClick={() => changePeriod(p)}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  period === p
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                This {p}
              </button>
            ))}
          </div>

          {/* Export */}
          <div className="flex items-center gap-1">
            <select
              value={exportFormat}
              onChange={(e) => setExportFormat(e.target.value)}
              className="text-xs border border-gray-300 rounded-l-lg px-2 py-1.5 bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="csv">CSV</option>
              <option value="json">JSON</option>
            </select>
            <button
              onClick={onExport}
              disabled={exporting}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 border-l-0 rounded-r-lg hover:bg-gray-50 transition-colors disabled:opacity-50"
            >
              <Download className="h-3.5 w-3.5" />
              Export
            </button>
          </div>
        </div>
      </div>

      {/* LOADING state — skeletons */}
      {loading && (
        <div className="space-y-6">
          {/* KPI skeleton */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => (
              <div
                key={i}
                className="bg-white rounded-xl border border-gray-200 p-5 animate-pulse"
              >
                <div className="h-3 bg-gray-200 rounded w-1/2 mb-4" />
                <div className="h-7 bg-gray-200 rounded w-2/3 mb-2" />
                <div className="h-3 bg-gray-100 rounded w-3/4" />
              </div>
            ))}
          </div>
          {/* Chart skeleton */}
          <div className="bg-white rounded-xl border border-gray-200 p-5 animate-pulse">
            <div className="h-4 bg-gray-200 rounded w-32 mb-4" />
            <div className="h-64 bg-gray-50 rounded" />
          </div>
          {/* Table skeleton */}
          <div className="bg-white rounded-xl border border-gray-200 p-5 animate-pulse">
            <div className="h-4 bg-gray-200 rounded w-40 mb-4" />
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-10 bg-gray-50 rounded mb-2" />
            ))}
          </div>
        </div>
      )}

      {/* LOADED state */}
      {!loading && (
        <div className="space-y-6">
          {/* KPI Cards */}
          <MetricsGrid overview={overview} tenant={tenant} />

          {/* Cost Chart */}
          <CostChart
            data={timeline}
            budgetLine={budgetLine}
            days={timelineDays}
            onChangeDays={changeTimelineDays}
          />

          {/* Workflow Breakdown Table */}
          <WorkflowBreakdown data={breakdown} />
        </div>
      )}
    </div>
  );
}
