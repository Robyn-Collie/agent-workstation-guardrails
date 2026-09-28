import { afterEach, describe, expect, it } from 'vitest';
import { main } from './cli.js';
import { compliantRepo, FixtureRepo } from './test/fixture-repo.js';

let repo: FixtureRepo;
afterEach(() => repo?.remove());

function run(args: string[]): { code: number; output: string } {
  let output = '';
  const code = main(args, (text) => (output += text));
  return { code, output };
}

describe('guardrail-check CLI', () => {
  it('exits 0 when every check passes', () => {
    repo = compliantRepo();
    const { code, output } = run([repo.root]);
    expect(code).toBe(0);
    expect(output).toContain('5 passed, 0 failed');
  });

  it('exits 1 and names each failing check', () => {
    // An empty git repo: only no-env-committed passes.
    repo = new FixtureRepo();
    const { code, output } = run([repo.root]);
    expect(code).toBe(1);
    expect(output).toContain('[FAIL] agents-md');
    expect(output).toContain('1 passed, 4 failed');
  });

  it('prints machine-readable results with --json', () => {
    repo = compliantRepo();
    const { output } = run(['--json', repo.root]);
    expect(JSON.parse(output).results).toHaveLength(5);
  });

  it('exits 2 on an unknown flag', () => {
    expect(run(['--nope']).code).toBe(2);
  });
});
