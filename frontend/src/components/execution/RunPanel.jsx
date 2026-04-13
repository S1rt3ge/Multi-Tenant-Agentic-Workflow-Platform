import { useState } from 'react';
import { Play, Square, Loader2, DollarSign, Zap, Clock } from 'lucide-react';

/**
 * RunPanel — form to launch executions and show progress.
 *
 * Shows:
 * - JSON input textarea
 * - Run / Cancel buttons
 * - Live progress (current step, cost counter)
 * - Execution status badge
 *
 * @param {object} props
 * @param {function} props.onStart - Called with parsed input data
 * @param {function} props.onCancel - Called to cancel execution
 * @param {object|null} props.execution - Current execution object
 * @param {object|null} props.currentStep - Current running step info
 * @param {number} props.totalSteps - Number of completed steps
 * @param {boolean} props.isStarting - Loading state for start
 * @param {boolean} props.isCancelling - Loading state for cancel
 * @param {boolean} props.isRunning - Is execution running
 * @param {boolean} props.canCancel - Can cancel execution
 * @param {boolean} props.isFinished - Is execution finished
 */
export default function RunPanel({
  onStart,
  onCancel,
  execution,
  currentStep,
  totalSteps,
  isStarting,
  isCancelling,
  isRunning,
  canCancel,
  isFinished,
}) {
  const [inputText, setInputText] = useState('{\n  "text": ""\n}');
  const [inputError, setInputError] = useState(null);

  const handleRun = () => {
    setInputError(null);
    try {
      const parsed = inputText.trim() ? JSON.parse(inputText) : null;
      onStart(parsed);
    } catch (e) {
      setInputError('Invalid JSON input');
    }
  };

  const statusColors = {
    pending: 'bg-yellow-100 text-yellow-800',
    running: 'bg-blue-100 text-blue-800',
    completed: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
    cancelled: 'bg-gray-100 text-gray-800',
  };

  return (
    <div className="bg-white border-b border-gray-200 p-4 space-y-4">
      {/* Input area */}
      {!execution && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Input Data (JSON)
          </label>
          <textarea
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            rows={4}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm font-mono focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-y"
            placeholder='{"text": "Analyze this document..."}'
          />
          {inputError && (
            <p className="mt-1 text-xs text-red-600">{inputError}</p>
          )}
        </div>
      )}

      {/* Action buttons */}
      <div className="flex items-center gap-3">
        {!execution && (
          <button
            onClick={handleRun}
            disabled={isStarting}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isStarting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            {isStarting ? 'Starting...' : 'Run Workflow'}
          </button>
        )}

        {canCancel && (
          <button
            onClick={onCancel}
            disabled={isCancelling}
            className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-md hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isCancelling ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Square className="h-4 w-4" />
            )}
            {isCancelling ? 'Cancelling...' : 'Cancel'}
          </button>
        )}

        {/* Status badge */}
        {execution && (
          <span
            className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
              statusColors[execution.status] || 'bg-gray-100 text-gray-800'
            }`}
          >
            {execution.status}
          </span>
        )}
      </div>

      {/* Progress indicators */}
      {execution && (
        <div className="flex items-center gap-6 text-sm text-gray-600">
          {/* Current step */}
          {currentStep && (
            <div className="flex items-center gap-1.5">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-500" />
              <span>
                Step {currentStep.stepNumber}: {currentStep.agentName}
              </span>
            </div>
          )}

          {/* Steps completed */}
          <div className="flex items-center gap-1.5">
            <Zap className="h-3.5 w-3.5 text-gray-400" />
            <span>{totalSteps} step{totalSteps !== 1 ? 's' : ''} completed</span>
          </div>

          {/* Token count */}
          <div className="flex items-center gap-1.5">
            <Clock className="h-3.5 w-3.5 text-gray-400" />
            <span>{(execution.total_tokens || 0).toLocaleString()} tokens</span>
          </div>

          {/* Cost */}
          <div className="flex items-center gap-1.5">
            <DollarSign className="h-3.5 w-3.5 text-gray-400" />
            <span>${(execution.total_cost || 0).toFixed(6)}</span>
          </div>
        </div>
      )}

      {/* Error message */}
      {execution?.error_message && (
        <div className="bg-red-50 border border-red-200 rounded-md p-3">
          <p className="text-sm text-red-700">{execution.error_message}</p>
        </div>
      )}

      {/* Output data */}
      {isFinished && execution?.output_data && (
        <div className="bg-gray-50 border border-gray-200 rounded-md p-3">
          <p className="text-xs font-medium text-gray-500 mb-1">Output</p>
          <pre className="text-sm text-gray-800 font-mono whitespace-pre-wrap overflow-auto max-h-40">
            {JSON.stringify(execution.output_data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
