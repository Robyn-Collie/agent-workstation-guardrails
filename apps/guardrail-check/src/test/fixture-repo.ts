import { execFileSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';

/** A throwaway git repository in the OS temp dir, built file by file. */
export class FixtureRepo {
  readonly root = mkdtempSync(join(tmpdir(), 'guardrail-check-'));

  constructor(options: { git?: boolean } = {}) {
    if (options.git ?? true)
      execFileSync('git', ['init', '-q'], { cwd: this.root });
  }

  write(path: string, content: string): this {
    const full = join(this.root, path);
    mkdirSync(dirname(full), { recursive: true });
    writeFileSync(full, content);
    return this;
  }

  /** Stage files so `git ls-files` sees them (no commit needed). */
  track(...paths: string[]): this {
    execFileSync('git', ['add', '--', ...paths], { cwd: this.root });
    return this;
  }

  remove(): void {
    rmSync(this.root, { recursive: true, force: true });
  }
}

/** A repo that satisfies every check. */
export function compliantRepo(): FixtureRepo {
  return new FixtureRepo()
    .write(
      'AGENTS.md',
      '# Agents\n\nEach agent works in its own worktree: `git worktree add ../agent-2`.\n',
    )
    .write(
      '.githooks/pre-commit',
      '#!/bin/sh\npython3 -m secret_scan --staged\n',
    )
    .write(
      '.devcontainer/devcontainer.json',
      '{\n  // comment\n  "remoteUser": "node",\n}\n',
    )
    .write('.env.example', 'API_KEY=\n')
    .track('.');
}
