import { describe, expect, it } from 'vitest';

import { validateGraph, isDuplicateEdge, isSelfLoop } from './graphValidation';


describe('graphValidation', () => {
  it('rejects missing agent configs', () => {
    const result = validateGraph(
      [{ id: 'node-1', data: { label: 'Agent' } }],
      [],
      [],
      'linear'
    );

    expect(result.valid).toBe(false);
    expect(result.errors.join('\n')).toContain('Nodes without agent configuration');
  });

  it('detects duplicate edges and self loops', () => {
    const edges = [{ source: 'a', target: 'b' }];

    expect(isDuplicateEdge(edges, 'a', 'b')).toBe(true);
    expect(isDuplicateEdge(edges, 'b', 'a')).toBe(false);
    expect(isSelfLoop('a', 'a')).toBe(true);
  });
});
