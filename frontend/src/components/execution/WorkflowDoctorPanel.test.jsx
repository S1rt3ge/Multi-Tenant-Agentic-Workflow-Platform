import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import WorkflowDoctorPanel from './WorkflowDoctorPanel';

describe('WorkflowDoctorPanel connector recovery', () => {
  it('renders an open credentials action for missing connector credentials', () => {
    const html = renderToStaticMarkup(
      <WorkflowDoctorPanel
        execution={{ id: 'exec-1', status: 'failed' }}
        initialSuggestions={[
          {
            id: 'suggestion-1',
            detector_code: 'missing_connector_credential',
            title: 'Connector credential is missing or inactive',
            root_cause: 'Connector credential is missing or inactive.',
            recommendation: 'Create or select a credential for the connector node.',
            severity: 'high',
            status: 'proposed',
            patch: { operations: [] },
          },
        ]}
        onOpenConnectorWorkspace={() => {}}
      />
    );

    expect(html).toContain('Open credentials');
    expect(html).toContain('Connector credential is missing');
  });
});
