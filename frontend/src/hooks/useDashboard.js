import { useState, useEffect, useCallback, useRef } from 'react';
import {
  fetchOverview,
  fetchCostTimeline,
  fetchWorkflowBreakdown,
  exportData,
} from '../api/analytics';

const REFRESH_INTERVAL = 60_000; // 60 seconds

/**
 * Hook for managing dashboard analytics state.
 * Auto-refreshes every 60 seconds.
 */
export default function useDashboard() {
  const [overview, setOverview] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [breakdown, setBreakdown] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [period, setPeriod] = useState('month');
  const [timelineDays, setTimelineDays] = useState(30);
  const [exporting, setExporting] = useState(false);

  const intervalRef = useRef(null);

  const loadAll = useCallback(async () => {
    setError(null);
    try {
      const [ov, tl, bd] = await Promise.all([
        fetchOverview(period),
        fetchCostTimeline(timelineDays),
        fetchWorkflowBreakdown(period),
      ]);
      setOverview(ov);
      setTimeline(tl);
      setBreakdown(bd);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load analytics');
    } finally {
      setLoading(false);
    }
  }, [period, timelineDays]);

  // Initial load + auto-refresh
  useEffect(() => {
    setLoading(true);
    loadAll();

    intervalRef.current = setInterval(loadAll, REFRESH_INTERVAL);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [loadAll]);

  const handleExport = useCallback(
    async (format = 'csv', from = null, to = null) => {
      setExporting(true);
      try {
        const result = await exportData({ format, from, to });
        return result;
      } finally {
        setExporting(false);
      }
    },
    []
  );

  const changePeriod = useCallback((newPeriod) => {
    setPeriod(newPeriod);
  }, []);

  const changeTimelineDays = useCallback((days) => {
    setTimelineDays(days);
  }, []);

  return {
    overview,
    timeline,
    breakdown,
    loading,
    error,
    period,
    timelineDays,
    exporting,
    refetch: loadAll,
    handleExport,
    changePeriod,
    changeTimelineDays,
  };
}
