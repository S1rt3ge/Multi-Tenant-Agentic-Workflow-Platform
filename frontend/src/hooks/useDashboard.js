import { useState, useEffect, useCallback, useRef } from 'react';
import {
  fetchOverview,
  fetchCostTimeline,
  fetchWorkflowBreakdown,
  fetchDispatchHealth,
  fetchDispatchAlertPolicy,
  fetchDispatchAlertChannels,
  fetchDispatchAlertDeliveries,
  fetchDispatchRunbook,
  acknowledgeDispatchIncident,
  fetchDispatchIncidentAnalytics,
  fetchDispatchControlRecommendations,
  fetchDispatchAutomationPlans,
  fetchDispatchIncidentHistory,
  previewDispatchAlertPolicy,
  resolveDispatchIncident,
  exportDispatchRunbook,
  createDispatchAutomationPlan,
  approveDispatchAutomationPlan,
  rejectDispatchAutomationPlan,
  fetchDispatchAutomationWorkerDiagnostics,
  fetchDispatchAutomationWorkerFleetDiagnostics,
  fetchDispatchAutomationWorkerConfig,
  fetchDispatchAutomationWorkerRuns,
  runDispatchAutomationWorker,
  updateDispatchAutomationWorkerConfig,
  exportData,
} from '../api/analytics';

const REFRESH_INTERVAL = 60_000; // 60 seconds

/**
 * Hook for managing dashboard analytics state.
 * Auto-refreshes every 60 seconds.
 */
export default function useDashboard(userRole = 'viewer') {
  const [overview, setOverview] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [breakdown, setBreakdown] = useState([]);
  const [dispatchHealth, setDispatchHealth] = useState(null);
  const [dispatchAlertPolicy, setDispatchAlertPolicy] = useState(null);
  const [dispatchAlertPreview, setDispatchAlertPreview] = useState(null);
  const [dispatchAlertChannels, setDispatchAlertChannels] = useState(null);
  const [dispatchAlertDeliveries, setDispatchAlertDeliveries] = useState(null);
  const [dispatchRunbook, setDispatchRunbook] = useState(null);
  const [dispatchIncidentAnalytics, setDispatchIncidentAnalytics] = useState(null);
  const [dispatchControlRecommendations, setDispatchControlRecommendations] = useState(null);
  const [dispatchAutomationPlans, setDispatchAutomationPlans] = useState(null);
  const [dispatchAutomationWorkerDiagnostics, setDispatchAutomationWorkerDiagnostics] = useState(null);
  const [dispatchAutomationWorkerFleetDiagnostics, setDispatchAutomationWorkerFleetDiagnostics] = useState(null);
  const [dispatchAutomationWorkerConfig, setDispatchAutomationWorkerConfig] = useState(null);
  const [dispatchAutomationWorkerRuns, setDispatchAutomationWorkerRuns] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [period, setPeriod] = useState('month');
  const [timelineDays, setTimelineDays] = useState(30);
  const [exporting, setExporting] = useState(false);
  const [acknowledging, setAcknowledging] = useState(false);
  const [resolving, setResolving] = useState(false);
  const [automationPlanBusy, setAutomationPlanBusy] = useState('');
  const [automationWorkerRunning, setAutomationWorkerRunning] = useState(false);
  const [automationWorkerResult, setAutomationWorkerResult] = useState(null);

  const intervalRef = useRef(null);

  const loadSchedulerDiagnostics = useCallback(async () => {
    if (userRole !== 'owner') return null;
    try {
      return await fetchDispatchAutomationWorkerDiagnostics();
    } catch (err) {
      if (err.response?.status === 403) return null;
      throw err;
    }
  }, [userRole]);

  const loadSchedulerFleetDiagnostics = useCallback(async () => {
    if (userRole !== 'platform_admin') return null;
    try {
      return await fetchDispatchAutomationWorkerFleetDiagnostics(true);
    } catch (err) {
      if (err.response?.status === 403) return null;
      throw err;
    }
  }, [userRole]);

  const loadAll = useCallback(async () => {
    // Each panel loads independently: one failing/slow endpoint must not blank
    // the whole dashboard (this runs on a 60s interval). Panels that fail keep
    // their previously loaded data; a global error is only shown if EVERYTHING
    // fails (e.g. auth/network outage).
    const tasks = [
      { run: () => fetchOverview(period), apply: (v) => setOverview(v) },
      { run: () => fetchCostTimeline(timelineDays), apply: (v) => setTimeline(v) },
      { run: () => fetchWorkflowBreakdown(period), apply: (v) => setBreakdown(v) },
      { run: () => fetchDispatchHealth(24), apply: (v) => setDispatchHealth(v) },
      { run: () => fetchDispatchIncidentAnalytics(30, 60), apply: (v) => setDispatchIncidentAnalytics(v) },
      { run: () => fetchDispatchControlRecommendations(24, 60), apply: (v) => setDispatchControlRecommendations(v) },
      { run: () => fetchDispatchAutomationPlans(), apply: (v) => setDispatchAutomationPlans(v) },
      { run: () => loadSchedulerDiagnostics(), apply: (v) => setDispatchAutomationWorkerDiagnostics(v) },
      { run: () => loadSchedulerFleetDiagnostics(), apply: (v) => setDispatchAutomationWorkerFleetDiagnostics(v) },
      { run: () => fetchDispatchAutomationWorkerConfig(), apply: (v) => setDispatchAutomationWorkerConfig(v) },
      { run: () => fetchDispatchAutomationWorkerRuns(), apply: (v) => setDispatchAutomationWorkerRuns(v) },
      { run: () => fetchDispatchAlertPolicy(), apply: (v) => setDispatchAlertPolicy(v) },
      { run: () => previewDispatchAlertPolicy(24), apply: (v) => setDispatchAlertPreview(v) },
      { run: () => fetchDispatchAlertChannels(), apply: (v) => setDispatchAlertChannels(v.items || []) },
      { run: () => fetchDispatchAlertDeliveries(), apply: (v) => setDispatchAlertDeliveries(v.items || []) },
    ];

    const results = await Promise.allSettled(tasks.map((t) => t.run()));
    results.forEach((result, i) => {
      if (result.status === 'fulfilled') {
        tasks[i].apply(result.value);
      }
    });

    // Runbook needs two endpoints merged; load them together but tolerate failure.
    const [runbookRes, historyRes] = await Promise.allSettled([
      fetchDispatchRunbook(24),
      fetchDispatchIncidentHistory(),
    ]);
    if (runbookRes.status === 'fulfilled') {
      const history =
        historyRes.status === 'fulfilled' ? historyRes.value.items || [] : [];
      setDispatchRunbook({ ...runbookRes.value, incident_history: history });
    }

    const allFailed = results.every((r) => r.status === 'rejected') && runbookRes.status === 'rejected';
    if (allFailed) {
      const firstError = results.find((r) => r.status === 'rejected');
      setError(firstError?.reason?.response?.data?.detail || 'Failed to load analytics');
    } else {
      setError(null);
    }
    setLoading(false);
  }, [loadSchedulerDiagnostics, loadSchedulerFleetDiagnostics, period, timelineDays]);

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

  const handleRunbookExport = useCallback(async () => {
    setExporting(true);
    try {
      return await exportDispatchRunbook(24);
    } finally {
      setExporting(false);
    }
  }, []);

  const handleIncidentAcknowledge = useCallback(async (note = 'Taking ownership from dashboard') => {
    setAcknowledging(true);
    try {
      const acknowledgement = await acknowledgeDispatchIncident(note);
      setDispatchRunbook((current) => (
        current ? { ...current, acknowledgement } : current
      ));
      return acknowledgement;
    } finally {
      setAcknowledging(false);
    }
  }, []);

  const handleIncidentResolve = useCallback(async (
    resolutionNote = 'Resolved from dashboard'
  ) => {
    setResolving(true);
    try {
      const resolved = await resolveDispatchIncident(resolutionNote);
      setDispatchRunbook((current) => (
        current
          ? {
            ...current,
            acknowledgement: null,
            incident_history: [resolved, ...(current.incident_history || [])],
          }
          : current
      ));
      return resolved;
    } finally {
      setResolving(false);
    }
  }, []);

  const upsertAutomationPlan = useCallback((plan) => {
    setDispatchAutomationPlans((current) => {
      const items = current?.items || [];
      const nextItems = [plan, ...items.filter((item) => item.id !== plan.id)];
      return { ...(current || {}), items: nextItems };
    });
    return plan;
  }, []);

  const handleAutomationPlanCreate = useCallback(async (recommendationCode) => {
    setAutomationPlanBusy(`create:${recommendationCode}`);
    try {
      const plan = await createDispatchAutomationPlan(recommendationCode);
      return upsertAutomationPlan(plan);
    } finally {
      setAutomationPlanBusy('');
    }
  }, [upsertAutomationPlan]);

  const handleAutomationPlanApprove = useCallback(async (planId) => {
    setAutomationPlanBusy(`approve:${planId}`);
    try {
      const plan = await approveDispatchAutomationPlan(planId);
      return upsertAutomationPlan(plan);
    } finally {
      setAutomationPlanBusy('');
    }
  }, [upsertAutomationPlan]);

  const handleAutomationPlanReject = useCallback(async (planId) => {
    setAutomationPlanBusy(`reject:${planId}`);
    try {
      const plan = await rejectDispatchAutomationPlan(planId);
      return upsertAutomationPlan(plan);
    } finally {
      setAutomationPlanBusy('');
    }
  }, [upsertAutomationPlan]);

  const handleAutomationWorkerRun = useCallback(async (limit = 10) => {
    setAutomationWorkerRunning(true);
    setAutomationPlanBusy('worker:run');
    try {
      const result = await runDispatchAutomationWorker(limit);
      const [plans, runs, diagnostics] = await Promise.all([
        fetchDispatchAutomationPlans(),
        fetchDispatchAutomationWorkerRuns(),
        loadSchedulerDiagnostics(),
      ]);
      setDispatchAutomationPlans(plans);
      setDispatchAutomationWorkerRuns(runs);
      setDispatchAutomationWorkerDiagnostics(diagnostics);
      setAutomationWorkerResult(result);
      return result;
    } finally {
      setAutomationPlanBusy('');
      setAutomationWorkerRunning(false);
    }
  }, [loadSchedulerDiagnostics]);

  const handleAutomationWorkerConfigUpdate = useCallback(async (config) => {
    setAutomationPlanBusy('worker:config');
    try {
      const updated = await updateDispatchAutomationWorkerConfig(config);
      const diagnostics = await loadSchedulerDiagnostics();
      setDispatchAutomationWorkerConfig(updated);
      setDispatchAutomationWorkerDiagnostics(diagnostics);
      return updated;
    } finally {
      setAutomationPlanBusy('');
    }
  }, [loadSchedulerDiagnostics]);

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
    dispatchHealth,
    dispatchIncidentAnalytics,
    dispatchControlRecommendations,
    dispatchAutomationPlans,
    dispatchAutomationWorkerDiagnostics,
    dispatchAutomationWorkerFleetDiagnostics,
    dispatchAutomationWorkerConfig,
    dispatchAutomationWorkerRuns,
    dispatchAlertPolicy,
    dispatchAlertPreview,
    dispatchAlertChannels,
    dispatchAlertDeliveries,
    dispatchRunbook,
    loading,
    error,
    period,
    timelineDays,
    exporting,
    acknowledging,
    resolving,
    automationPlanBusy,
    automationWorkerRunning,
    automationWorkerResult,
    refetch: loadAll,
    handleExport,
    handleRunbookExport,
    handleIncidentAcknowledge,
    handleIncidentResolve,
    handleAutomationPlanCreate,
    handleAutomationPlanApprove,
    handleAutomationPlanReject,
    handleAutomationWorkerRun,
    handleAutomationWorkerConfigUpdate,
    changePeriod,
    changeTimelineDays,
  };
}
