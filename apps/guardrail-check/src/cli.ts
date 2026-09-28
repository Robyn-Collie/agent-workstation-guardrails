#!/usr/bin/env node
import { realpathSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';
import { runChecks } from './lib/checks.js';
import { formatReport } from './lib/report.js';

const USAGE = 'Usage: guardrail-check [--json] [path]';

/** Returns the process exit code: 0 all passed, 1 a check failed, 2 bad usage. */
export function main(argv: string[], write: (text: string) => void): number {
  let parsed;
  try {
    parsed = parseArgs({
      args: argv,
      options: {
        json: { type: 'boolean' },
        help: { type: 'boolean', short: 'h' },
      },
      allowPositionals: true,
    });
  } catch (error) {
    write(`${(error as Error).message}\n${USAGE}`);
    return 2;
  }
  if (parsed.values.help) {
    write(USAGE);
    return 0;
  }
  if (parsed.positionals.length > 1) {
    write(USAGE);
    return 2;
  }

  const root = resolve(parsed.positionals[0] ?? '.');
  const results = runChecks(root);
  write(
    parsed.values.json
      ? JSON.stringify({ root, results }, null, 2)
      : formatReport(root, results),
  );
  return results.every((r) => r.passed) ? 0 : 1;
}

// Run only when executed directly (including through an npm bin symlink),
// not when imported by tests.
const invokedAs = process.argv[1]
  ? pathToFileURL(realpathSync(process.argv[1])).href
  : '';
if (import.meta.url === invokedAs) {
  process.exitCode = main(process.argv.slice(2), (text) => console.log(text));
}
