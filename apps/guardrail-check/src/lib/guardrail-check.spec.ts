import { guardrailCheck } from './guardrail-check.js';

describe('guardrailCheck', () => {
  it('should work', () => {
    expect(guardrailCheck()).toEqual('guardrail-check');
  });
});
