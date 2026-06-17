import { X } from 'lucide-react';
import CredentialManager from './CredentialManager';
import DispatchQueuePanel from './DispatchQueuePanel';
import WebhookTriggerPanel from './WebhookTriggerPanel';

export default function ConnectorWorkspacePanel({
  canManage = false,
  credentials = [],
  triggers = [],
  dispatchExecutions = [],
  loadingCredentials = false,
  loadingTriggers = false,
  loadingDispatchExecutions = false,
  retryingDispatchExecutionId = '',
  credentialError = '',
  triggerError = '',
  dispatchError = '',
  onCreateCredential,
  onDeleteCredential,
  onCreateWebhook,
  onCopyWebhook,
  onRefreshDispatchQueue,
  onRetryDispatchExecution,
  onClose,
}) {
  return (
    <aside className="w-[420px] bg-white border-l border-gray-200 flex flex-col h-full">
      <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-gray-900">Connector workspace</h2>
          <p className="text-xs text-gray-500">Credentials, triggers, and dispatch queue</p>
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
            title="Close connectors"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="h-[38%] min-h-[260px] border-b border-gray-200">
          <CredentialManager
            canManage={canManage}
            credentials={credentials}
            loading={loadingCredentials}
            error={credentialError}
            onCreate={onCreateCredential}
            onDelete={onDeleteCredential}
          />
        </div>

        <div className="p-4 space-y-4">
          <WebhookTriggerPanel
            canManage={canManage}
            triggers={triggers}
            loading={loadingTriggers}
            error={triggerError}
            onCreate={onCreateWebhook}
            onCopy={onCopyWebhook}
          />
          <DispatchQueuePanel
            canManage={canManage}
            executions={dispatchExecutions}
            loading={loadingDispatchExecutions}
            error={dispatchError}
            onRefresh={onRefreshDispatchQueue}
            onRetry={onRetryDispatchExecution}
            retryingExecutionId={retryingDispatchExecutionId}
          />
        </div>
      </div>
    </aside>
  );
}
