import { useState, useMemo } from 'react';
import {
  ChevronDown,
  ChevronRight,
  Clock,
  DollarSign,
  Zap,
  AlertCircle,
  CheckCircle2,
  MessageSquare,
  Wrench,
  Brain,
  Filter,
} from 'lucide-react';

/**
 * LogViewer — displays execution step logs as a timeline.
 *
 * Features:
 * - Color-coded steps (green=success, red=error, gray=pending)
 * - Expandable details (input, output, reasoning)
 * - Filter by agent name
 *
 * @param {object} props
 * @param {Array} props.logs - Execution log entries
 * @param {object|null} props.currentStep - Currently running step
 */
export default function LogViewer({ logs, currentStep }) {
  const [expandedSteps, setExpandedSteps] = useState(new Set());
  const [filterAgent, setFilterAgent] = useState('');

  // Unique agent names for filter
  const agentNames = useMemo(() => {
    const names = new Set(logs.map((l) => l.agent_name));
    return Array.from(names).sort();
  }, [logs]);

  // Filtered logs
  const filteredLogs = useMemo(() => {
    if (!filterAgent) return logs;
    return logs.filter((l) => l.agent_name === filterAgent);
  }, [logs, filterAgent]);

  const toggleStep = (index) => {
    setExpandedSteps((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  const actionIcon = (action) => {
    switch (action) {
      case 'llm_call':
        return <Brain className="h-4 w-4" />;
      case 'tool_call':
        return <Wrench className="h-4 w-4" />;
      case 'decision':
        return <MessageSquare className="h-4 w-4" />;
      case 'error':
        return <AlertCircle className="h-4 w-4" />;
      default:
        return <Zap className="h-4 w-4" />;
    }
  };

  const actionColor = (action) => {
    switch (action) {
      case 'error':
        return 'text-red-600 bg-red-50 border-red-200';
      case 'llm_call':
        return 'text-green-600 bg-green-50 border-green-200';
      case 'tool_call':
        return 'text-blue-600 bg-blue-50 border-blue-200';
      case 'decision':
        return 'text-yellow-600 bg-yellow-50 border-yellow-200';
      default:
        return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  const dotColor = (action) => {
    switch (action) {
      case 'error':
        return 'bg-red-500';
      case 'llm_call':
        return 'bg-green-500';
      case 'tool_call':
        return 'bg-blue-500';
      case 'decision':
        return 'bg-yellow-500';
      default:
        return 'bg-gray-400';
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header with filter */}
      <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between bg-white">
        <h3 className="text-sm font-semibold text-gray-700">
          Execution Logs ({filteredLogs.length})
        </h3>
        {agentNames.length > 1 && (
          <div className="flex items-center gap-2">
            <Filter className="h-3.5 w-3.5 text-gray-400" />
            <select
              value={filterAgent}
              onChange={(e) => setFilterAgent(e.target.value)}
              className="text-xs border border-gray-300 rounded px-2 py-1 bg-white focus:ring-1 focus:ring-blue-500"
            >
              <option value="">All agents</option>
              {agentNames.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Log timeline */}
      <div className="flex-1 overflow-y-auto p-4">
        {filteredLogs.length === 0 && !currentStep && (
          <div className="flex flex-col items-center justify-center h-full text-gray-400">
            <Clock className="h-8 w-8 mb-2" />
            <p className="text-sm">No logs yet. Run the workflow to see execution steps.</p>
          </div>
        )}

        <div className="space-y-1">
          {filteredLogs.map((log, index) => {
            const isExpanded = expandedSteps.has(index);
            const colorClass = actionColor(log.action);

            return (
              <div key={index} className="relative">
                {/* Timeline line */}
                {index < filteredLogs.length - 1 && (
                  <div className="absolute left-[11px] top-8 bottom-0 w-px bg-gray-200" />
                )}

                {/* Step row */}
                <div
                  onClick={() => toggleStep(index)}
                  className="flex items-start gap-3 cursor-pointer hover:bg-gray-50 rounded-md p-2 transition-colors"
                >
                  {/* Timeline dot */}
                  <div className={`mt-1 h-[10px] w-[10px] rounded-full flex-shrink-0 ${dotColor(log.action)}`} />

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      {isExpanded ? (
                        <ChevronDown className="h-3.5 w-3.5 text-gray-400 flex-shrink-0" />
                      ) : (
                        <ChevronRight className="h-3.5 w-3.5 text-gray-400 flex-shrink-0" />
                      )}
                      <span className="text-xs text-gray-400 font-mono flex-shrink-0">
                        #{log.step_number}
                      </span>
                      <span className="text-sm font-medium text-gray-800 truncate">
                        {log.agent_name}
                      </span>
                      <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium ${colorClass}`}>
                        {actionIcon(log.action)}
                        {log.action}
                      </span>
                    </div>

                    {/* Summary line */}
                    <div className="flex items-center gap-4 mt-1 ml-5 text-xs text-gray-500">
                      {log.tokens_used > 0 && (
                        <span className="flex items-center gap-1">
                          <Zap className="h-3 w-3" />
                          {log.tokens_used.toLocaleString()} tokens
                        </span>
                      )}
                      {log.cost > 0 && (
                        <span className="flex items-center gap-1">
                          <DollarSign className="h-3 w-3" />
                          ${log.cost.toFixed(6)}
                        </span>
                      )}
                      {log.duration_ms > 0 && (
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {log.duration_ms}ms
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Expanded details */}
                {isExpanded && (
                  <div className="ml-9 mt-1 mb-3 space-y-2">
                    {log.decision_reasoning && (
                      <div className="bg-yellow-50 border border-yellow-200 rounded p-2">
                        <p className="text-xs font-medium text-yellow-700 mb-1">Reasoning</p>
                        <p className="text-xs text-yellow-800 whitespace-pre-wrap">
                          {log.decision_reasoning}
                        </p>
                      </div>
                    )}

                    {log.input_data && (
                      <div className="bg-gray-50 border border-gray-200 rounded p-2">
                        <p className="text-xs font-medium text-gray-500 mb-1">Input</p>
                        <pre className="text-xs text-gray-700 font-mono whitespace-pre-wrap overflow-auto max-h-32">
                          {JSON.stringify(log.input_data, null, 2)}
                        </pre>
                      </div>
                    )}

                    {log.output_data && (
                      <div className="bg-gray-50 border border-gray-200 rounded p-2">
                        <p className="text-xs font-medium text-gray-500 mb-1">Output</p>
                        <pre className="text-xs text-gray-700 font-mono whitespace-pre-wrap overflow-auto max-h-32">
                          {JSON.stringify(log.output_data, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}

          {/* Currently running step indicator */}
          {currentStep && (
            <div className="relative">
              <div className="flex items-start gap-3 p-2">
                <div className="mt-1 h-[10px] w-[10px] rounded-full flex-shrink-0 bg-blue-500 animate-pulse" />
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-400 font-mono">
                    #{currentStep.stepNumber}
                  </span>
                  <span className="text-sm font-medium text-blue-600">
                    {currentStep.agentName}
                  </span>
                  <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-700">
                    <svg className="h-3 w-3 animate-spin" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    running
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
