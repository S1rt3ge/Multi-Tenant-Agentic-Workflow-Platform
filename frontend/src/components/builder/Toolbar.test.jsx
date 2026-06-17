import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import Toolbar from './Toolbar';

describe('Toolbar connector workspace action', () => {
  it('renders a connector workspace button', () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <Toolbar
          workflowName="Connector Flow"
          onSave={() => {}}
          onRun={() => {}}
          onValidate={() => {}}
          onUndo={() => {}}
          onRedo={() => {}}
          onZoomIn={() => {}}
          onZoomOut={() => {}}
          onFitView={() => {}}
          onOpenConnectors={() => {}}
        />
      </MemoryRouter>
    );

    expect(html).toContain('Connectors');
  });
});
