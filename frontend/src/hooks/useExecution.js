import { useState, useEffect, useCallback, useRef } from 'react';
import {
  getExecution,
  getExecutionLogs,
  startExecution,
  cancelExecution,
  getExecutionStreamUrlWithAuth,
} from '../api/executions';
import toast from 'react-hot-toast';


function encodeTokenForProtocol(token) {
  if (!token) return null;

  const utf8 = encodeURIComponent(token).replace(
    /%([0-9A-F]{2})/g,
    (_, hex) => String.fromCharCode(parseInt(hex, 16))
  );

  return btoa(utf8)
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/g, '');
}

/**
 * useExecution — manages execution state, WebSocket streaming, and actions.
 *
 * @param {string} executionId - Execution UUID (null to start fresh)
 * @param {string} workflowId - Workflow UUID
 * @returns {object} Execution state and handlers
 */
export default function useExecution(executionId, workflowId) {
  const [execution, setExecution] = useState(null);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isStarting, setIsStarting] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [currentStep, setCurrentStep] = useState(null);

  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const currentExecutionIdRef = useRef(executionId || null);

  useEffect(() => {
    currentExecutionIdRef.current = executionId || execution?.id || null;
  }, [executionId, execution?.id]);

  // --- Fetch execution + logs ---
  const fetchExecution = useCallback(async (execId) => {
    if (!execId) return;
    setLoading(true);
    setError(null);
    try {
      const [exec, execLogs] = await Promise.all([
        getExecution(execId),
        getExecutionLogs(execId),
      ]);
      setExecution(exec);
      setLogs(execLogs);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load execution');
    } finally {
      setLoading(false);
    }
  }, []);

  // --- Load execution on mount / ID change ---
  useEffect(() => {
    if (executionId) {
      fetchExecution(executionId);
    }
  }, [executionId, fetchExecution]);

  // --- WebSocket connection for live streaming ---
  const connectWebSocket = useCallback((execId) => {
    if (!execId) return;

    // Close existing connection
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    const token = localStorage.getItem('access_token');
    if (!token) {
      return;
    }
    const encodedToken = encodeTokenForProtocol(token);
    const streamConnection = getExecutionStreamUrlWithAuth(execId, encodedToken);
    const ws = new WebSocket(streamConnection.url, streamConnection.protocols);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);

        if (msg.type === 'ping') return;

        if (msg.type === 'step_start') {
          setCurrentStep({
            agentName: msg.data.agent_name,
            stepNumber: msg.data.step_number,
          });
        }

        if (msg.type === 'step_complete') {
          setLogs((prev) => [
            ...prev,
            {
              step_number: msg.data.step_number,
              agent_name: msg.data.agent_name,
              action: msg.data.action || 'llm_call',
              tokens_used: msg.data.tokens || 0,
              cost: msg.data.cost || 0,
              duration_ms: msg.data.duration_ms || 0,
              output_data: msg.data.output_data || null,
              input_data: msg.data.input_data || null,
              decision_reasoning: msg.data.decision_reasoning || null,
              created_at: new Date().toISOString(),
            },
          ]);

          // Update execution totals
          setExecution((prev) =>
            prev
              ? {
                  ...prev,
                  total_tokens: (prev.total_tokens || 0) + (msg.data.tokens || 0),
                  total_cost: (prev.total_cost || 0) + (msg.data.cost || 0),
                  status: 'running',
                }
              : prev
          );
          setCurrentStep(null);
        }

        if (msg.type === 'execution_complete') {
          setExecution((prev) =>
            prev
              ? {
                  ...prev,
                  status: msg.data.status || 'completed',
                  total_tokens: msg.data.total_tokens ?? prev.total_tokens,
                  total_cost: msg.data.total_cost ?? prev.total_cost,
                  output_data: msg.data.output_data ?? prev.output_data,
                  completed_at: new Date().toISOString(),
                }
              : prev
          );
          setCurrentStep(null);
          const latestExecId = currentExecutionIdRef.current;
          if (latestExecId) {
            fetchExecution(latestExecId);
          }
          ws.close();
        }

        if (msg.type === 'error') {
          setLogs((prev) => [
            ...prev,
            {
              step_number: msg.data.step_number || (prev.length + 1),
              agent_name: msg.data.agent_name || 'System',
              action: 'error',
              tokens_used: 0,
              cost: 0,
              duration_ms: 0,
              output_data: { error: msg.data.message },
              input_data: null,
              decision_reasoning: null,
              created_at: new Date().toISOString(),
            },
          ]);

          if (msg.data.fatal) {
            setExecution((prev) =>
              prev
                ? {
                    ...prev,
                    status: 'failed',
                    error_message: msg.data.message,
                  }
                : prev
            );
            setCurrentStep(null);
          }
        }
      } catch (e) {
        // Ignore malformed messages
      }
    };

    ws.onerror = () => {
      // Errors handled by onclose
    };

    ws.onclose = () => {
      if (wsRef.current === ws) {
        wsRef.current = null;
      }
    };
  }, [fetchExecution]);

  // --- Auto-connect WebSocket when execution is running ---
  useEffect(() => {
    if ((execution?.status === 'running' || execution?.status === 'pending') && executionId && !wsRef.current) {
      connectWebSocket(executionId);
    }
    return undefined;
  }, [execution?.status, executionId, connectWebSocket]);

  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, []);

  // --- Start execution ---
  const handleStart = useCallback(
    async (inputData = null) => {
      if (!workflowId) return;
      setIsStarting(true);
      setError(null);
      try {
        const result = await startExecution(workflowId, inputData);
        const execId = result.execution_id;

        // Fetch the full execution object
        const exec = await getExecution(execId);
        setExecution(exec);
        setLogs([]);
        setCurrentStep(null);

        // Connect WebSocket for live updates
        connectWebSocket(execId);

        toast.success('Execution started');
        return execId;
      } catch (err) {
        const msg = err.response?.data?.detail || 'Failed to start execution';
        setError(msg);
        toast.error(msg);
        return null;
      } finally {
        setIsStarting(false);
      }
    },
    [workflowId, connectWebSocket]
  );

  // --- Cancel execution ---
  const handleCancel = useCallback(async () => {
    if (!execution?.id) return;
    setIsCancelling(true);
    try {
      const updated = await cancelExecution(execution.id);
      setExecution(updated);
      setCurrentStep(null);
      toast.success('Execution cancelled');
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to cancel execution';
      toast.error(msg);
    } finally {
      setIsCancelling(false);
    }
  }, [execution?.id]);

  // --- Computed values ---
  const isRunning = execution?.status === 'running';
  const isPending = execution?.status === 'pending';
  const isFinished = ['completed', 'failed', 'cancelled'].includes(execution?.status);
  const canCancel = isRunning || isPending;
  const totalSteps = logs.length;

  return {
    // State
    execution,
    logs,
    loading,
    error,
    isStarting,
    isCancelling,
    currentStep,

    // Computed
    isRunning,
    isPending,
    isFinished,
    canCancel,
    totalSteps,

    // Actions
    onStart: handleStart,
    onCancel: handleCancel,
    refetch: () => fetchExecution(executionId || execution?.id),
  };
}
