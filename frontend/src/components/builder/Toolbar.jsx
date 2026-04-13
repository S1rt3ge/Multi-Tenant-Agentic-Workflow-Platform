import {
  Save,
  Play,
  CheckCircle,
  ZoomIn,
  ZoomOut,
  Maximize,
  Undo2,
  Redo2,
  ArrowLeft,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';

/**
 * Toolbar — top bar with Save, Run, Validate, Zoom controls, Undo/Redo.
 *
 * @param {Object} props
 * @param {Function} props.onSave - Save handler
 * @param {Function} props.onRun - Run handler
 * @param {Function} props.onValidate - Validate handler
 * @param {Function} props.onUndo - Undo handler
 * @param {Function} props.onRedo - Redo handler
 * @param {Function} props.onZoomIn - Zoom in handler
 * @param {Function} props.onZoomOut - Zoom out handler
 * @param {Function} props.onFitView - Fit view handler
 * @param {boolean} props.canUndo - Whether undo is available
 * @param {boolean} props.canRedo - Whether redo is available
 * @param {boolean} props.isSaving - Whether save is in progress
 * @param {boolean} props.hasUnsavedChanges - Whether there are unsaved changes
 * @param {boolean} props.disabled - If viewer role — hide Save/Run
 * @param {string} props.workflowName - Workflow name for display
 */
export default function Toolbar({
  onSave,
  onRun,
  onValidate,
  onUndo,
  onRedo,
  onZoomIn,
  onZoomOut,
  onFitView,
  canUndo = false,
  canRedo = false,
  isSaving = false,
  hasUnsavedChanges = false,
  disabled = false,
  workflowName = 'Workflow',
}) {
  const navigate = useNavigate();

  return (
    <div className="h-12 bg-white border-b border-gray-200 flex items-center justify-between px-4 flex-shrink-0">
      {/* Left section: Back + workflow name */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate('/workflows')}
          className="p-1.5 rounded-md text-gray-500 hover:bg-gray-100 hover:text-gray-700 transition-colors"
          title="Back to Workflows"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div className="flex items-center gap-2">
          <h1 className="text-sm font-semibold text-gray-900 truncate max-w-[200px]">
            {workflowName}
          </h1>
          {hasUnsavedChanges && (
            <span className="w-2 h-2 rounded-full bg-orange-400" title="Unsaved changes" />
          )}
          {isSaving && (
            <span className="text-xs text-gray-400">Saving...</span>
          )}
        </div>
      </div>

      {/* Center section: Undo/Redo + Zoom controls */}
      <div className="flex items-center gap-1">
        <button
          onClick={onUndo}
          disabled={!canUndo}
          className="p-1.5 rounded-md text-gray-500 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          title="Undo (Ctrl+Z)"
        >
          <Undo2 className="h-4 w-4" />
        </button>
        <button
          onClick={onRedo}
          disabled={!canRedo}
          className="p-1.5 rounded-md text-gray-500 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          title="Redo (Ctrl+Shift+Z)"
        >
          <Redo2 className="h-4 w-4" />
        </button>

        <div className="w-px h-5 bg-gray-200 mx-1" />

        <button
          onClick={onZoomOut}
          className="p-1.5 rounded-md text-gray-500 hover:bg-gray-100 transition-colors"
          title="Zoom Out"
        >
          <ZoomOut className="h-4 w-4" />
        </button>
        <button
          onClick={onZoomIn}
          className="p-1.5 rounded-md text-gray-500 hover:bg-gray-100 transition-colors"
          title="Zoom In"
        >
          <ZoomIn className="h-4 w-4" />
        </button>
        <button
          onClick={onFitView}
          className="p-1.5 rounded-md text-gray-500 hover:bg-gray-100 transition-colors"
          title="Fit View"
        >
          <Maximize className="h-4 w-4" />
        </button>
      </div>

      {/* Right section: Validate, Save, Run */}
      <div className="flex items-center gap-2">
        <button
          onClick={onValidate}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md border border-gray-200 text-gray-700 hover:bg-gray-50 transition-colors"
        >
          <CheckCircle className="h-3.5 w-3.5" />
          Validate
        </button>

        {!disabled && (
          <>
            <button
              onClick={onSave}
              disabled={isSaving}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md border border-gray-200 text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors"
              title="Save (Ctrl+S)"
            >
              <Save className="h-3.5 w-3.5" />
              Save
            </button>

            <button
              onClick={onRun}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md bg-blue-600 text-white hover:bg-blue-700 transition-colors"
            >
              <Play className="h-3.5 w-3.5" />
              Run
            </button>
          </>
        )}
      </div>
    </div>
  );
}
