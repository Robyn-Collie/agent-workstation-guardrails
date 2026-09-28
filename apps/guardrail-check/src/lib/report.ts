import type { CheckResult } from './types.js';

export function formatReport(root: string, results: CheckResult[]): string {
  const failed = results.filter((r) => !r.passed).length;
  const lines = [`guardrail-check: ${root}`, ''];
  for (const r of results) {
    lines.push(`[${r.passed ? 'PASS' : 'FAIL'}] ${r.id}: ${r.title}`);
    lines.push(`       ${r.detail}`);
  }
  lines.push('', `${results.length - failed} passed, ${failed} failed`);
  return lines.join('\n');
}
