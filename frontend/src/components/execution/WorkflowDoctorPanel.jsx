import { useCallback, useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import {
  AlertCircle,
  CheckCircle2,
  Loader2,
  Play,
  RefreshCw,
  ShieldCheck,
  Wrench,
  XCircle,
  KeyRound,
} from 'lucide-react';
import {
  applyFixSuggestion,
  diagnoseExecution,
  dismissFixSuggestion,
  listFixSuggestions,
  replayFixSuggestion,
} from '../../api/executions';

const DIAGNOSABLE_STATUSES = new Set(['failed', 'cancelled']);
const EMPTY_SUGGESTIONS = [];

const severityClasses = {
  critical: 'bg-red-100 text-red-800 border-red-200',
  high: 'bg-orange-100 text-orange-800 border-orange-200',
  medium: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  low: 'bg-gray-100 text-gray-700 border-gray-200',
};

const statusClasses = {
  proposed: 'bg-blue-50 text-blue-700 border-blue-200',
  replay_passed: 'bg-green-50 text-green-700 border-green-200',
  replay_failed: 'bg-red-50 text-red-700 border-red-200',
  applied: 'bg-purple-50 text-purple-700 border-purple-200',
  dismissed: 'bg-gray-50 text-gray-600 border-gray-200',
};

function getPatchText(operation) {
  if (operation.target_type === 'agent_config' && operation.path === '/model') {
    return `Set agent model to ${operation.value}`;
  }
  if (operation.target_type === 'tool' && operation.path === '/config/url') {
    return `Set tool URL to ${operation.value}`;
  }
  if (operation.target_type === 'tool' && operation.path === '/config/method') {
    return `Set tool method to ${operation.value}`;
  }
  return `${operation.op} ${operation.target_type}${operation.path}`;
}

function IconButton({ children, disabled, icon: Icon, onClick, tone = 'neutral' }) {
  const tones = {
    neutral: 'border-gray-300 text-gray-700 hover:bg-gray-50',
    primary: 'border-blue-600 bg-blue-600 text-white hover:bg-blue-700',
    success: 'border-green-600 bg-green-600 text-white hover:bg-green-700',
    danger: 'border-red-300 text-red-700 hover:bg-red-50',
  };

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-md border transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${tones[tone]}`}
    >
      <Icon className="h-3.5 w-3.5" />
      {children}
    </button>
  );
}

export default function WorkflowDoctorPanel({
  execution,
  onRetryCreated,
  onOpenConnectorWorkspace,
  initialSuggestions = EMPTY_SUGGESTIONS,
}) {
  const [suggestions, setSuggestions] = useState(initialSuggestions);
  const [loading, setLoading] = useState(false);
  const [busyKey, setBusyKey] = useState(null);
  const [error, setError] = useState(null);

  const canDiagnose = DIAGNOSABLE_STATUSES.has(execution?.status);

  const loadSuggestions = useCallback(async () => {
    if (!execution?.id || !canDiagnose) return;
    setLoading(true);
    setError(null);
    try {
      const data = await listFixSuggestions(execution.id);
      setSuggestions(data.items || []);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load fix suggestions');
    } finally {
      setLoading(false);
    }
  }, [canDiagnose, execution?.id]);

  useEffect(() => {
    setSuggestions(initialSuggestions);
    setError(null);
    if (canDiagnose && initialSuggestions.length === 0) {
      loadSuggestions();
    }
  }, [canDiagnose, initialSuggestions, loadSuggestions]);

  if (!canDiagnose) {
    return null;
  }

  const runAction = async (key, action) => {
    setBusyKey(key);
    setError(null);
    try {
      await action();
    } catch (err) {
      const message = err.response?.data?.detail || 'Workflow Doctor action failed';
      setError(message);
      toast.error(message);
    } finally {
      setBusyKey(null);
    }
  };

  const handleDiagnose = () => runAction('diagnose', async () => {
    const data = await diagnoseExecution(execution.id);
    setSuggestions(data.items || []);
    toast.success('Diagnosis ready');
  });

  const handleReplay = (suggestion) => runAction(`replay-${suggestion.id}`, async () => {
    const replay = await replayFixSuggestion(suggestion.id);
    setSuggestions((items) => items.map((item) => (
      item.id === suggestion.id
        ? {
            ...item,
            status: replay.status === 'passed' ? 'replay_passed' : 'replay_failed',
            replay_result: replay.result,
          }
        : item
    )));
    toast.success(replay.status === 'passed' ? 'Replay passed' : 'Replay finished');
  });

  const handleApply = (suggestion) => runAction(`apply-${suggestion.id}`, async () => {
    const result = await applyFixSuggestion(suggestion.id, { retry: true });
    setSuggestions((items) => items.map((item) => (
      item.id === suggestion.id ? { ...item, status: 'applied' } : item
    )));
    toast.success('Fix applied');
    if (result.retry_execution_id) {
      onRetryCreated?.(result.retry_execution_id);
    }
  });

  const handleDismiss = (suggestion) => runAction(`dismiss-${suggestion.id}`, async () => {
    await dismissFixSuggestion(suggestion.id);
    setSuggestions((items) => items.filter((item) => item.id !== suggestion.id));
    toast.success('Suggestion dismissed');
  });

  return (
    <div className="border-b border-gray-200 bg-white">
      <div className="px-4 py-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <Wrench className="h-4 w-4 text-blue-600 flex-shrink-0" />
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-gray-800">Workflow Doctor</h3>
            <p className="text-xs text-gray-500 truncate">
              {suggestions.length ? `${suggestions.length} suggestion${suggestions.length === 1 ? '' : 's'}` : 'Ready'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <IconButton
            icon={RefreshCw}
            onClick={loadSuggestions}
            disabled={loading || !!busyKey}
          >
            Refresh
          </IconButton>
          <IconButton
            icon={AlertCircle}
            onClick={handleDiagnose}
            disabled={loading || !!busyKey}
            tone="primary"
          >
            Diagnose
          </IconButton>
        </div>
      </div>

      {error && (
        <div className="mx-4 mb-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          {error}
        </div>
      )}

      <div className="max-h-[340px] overflow-y-auto px-4 pb-4">
        {loading && (
          <div className="flex items-center gap-2 py-3 text-sm text-gray-500">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading suggestions...
          </div>
        )}

        {!loading && suggestions.length === 0 && (
          <div className="rounded-md border border-dashed border-gray-300 px-3 py-4 text-sm text-gray-500">
            No suggestions yet.
          </div>
        )}

        <div className="space-y-3">
          {suggestions.map((suggestion) => {
            const operations = suggestion.patch?.operations || [];
            const hasPatch = operations.length > 0;
            const isApplied = suggestion.status === 'applied';
            const replayPassed = suggestion.status === 'replay_passed';
            const isMissingConnectorCredential =
              suggestion.detector_code === 'missing_connector_credential';

            return (
              <div key={suggestion.id} className="rounded-md border border-gray-200 p-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-semibold text-gray-800">
                        {suggestion.title}
                      </p>
                      <span className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[11px] font-medium ${severityClasses[suggestion.severity] || severityClasses.low}`}>
                        {suggestion.severity}
                      </span>
                      <span className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[11px] font-medium ${statusClasses[suggestion.status] || statusClasses.proposed}`}>
                        {suggestion.status}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-gray-600">
                      {suggestion.root_cause}
                    </p>
                  </div>
                  {suggestion.status === 'replay_passed' && (
                    <ShieldCheck className="h-4 w-4 text-green-600 flex-shrink-0" />
                  )}
                  {suggestion.status === 'replay_failed' && (
                    <XCircle className="h-4 w-4 text-red-600 flex-shrink-0" />
                  )}
                </div>

                <p className="mt-2 text-xs text-gray-500">
                  {suggestion.recommendation}
                </p>

                {hasPatch ? (
                  <div className="mt-3 space-y-1">
                    {operations.map((operation, index) => (
                      <div
                        key={`${suggestion.id}-${index}`}
                        className="rounded bg-gray-50 px-2 py-1.5 text-xs font-mono text-gray-700"
                      >
                        {getPatchText(operation)}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="mt-3 rounded bg-gray-50 px-2 py-1.5 text-xs text-gray-600">
                    Manual fix required
                  </div>
                )}

                {suggestion.replay_result?.message && (
                  <div className="mt-3 flex items-center gap-1.5 text-xs text-green-700">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    {suggestion.replay_result.message}
                  </div>
                )}

                <div className="mt-3 flex flex-wrap items-center gap-2">
                  {hasPatch && (
                    <IconButton
                      icon={Play}
                      onClick={() => handleReplay(suggestion)}
                      disabled={isApplied || !!busyKey}
                    >
                      {busyKey === `replay-${suggestion.id}` ? 'Replaying...' : 'Replay'}
                    </IconButton>
                  )}
                  {hasPatch && (
                    <IconButton
                      icon={Wrench}
                      onClick={() => handleApply(suggestion)}
                      disabled={isApplied || !!busyKey || (!replayPassed && suggestion.status !== 'proposed')}
                      tone="success"
                    >
                      {busyKey === `apply-${suggestion.id}` ? 'Applying...' : 'Apply & retry'}
                    </IconButton>
                  )}
                  {isMissingConnectorCredential && onOpenConnectorWorkspace && (
                    <IconButton
                      icon={KeyRound}
                      onClick={onOpenConnectorWorkspace}
                      disabled={!!busyKey}
                      tone="primary"
                    >
                      Open credentials
                    </IconButton>
                  )}
                  {!isApplied && (
                    <IconButton
                      icon={XCircle}
                      onClick={() => handleDismiss(suggestion)}
                      disabled={!!busyKey}
                      tone="danger"
                    >
                      Dismiss
                    </IconButton>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
