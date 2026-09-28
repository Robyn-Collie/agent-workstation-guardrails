import { afterEach, describe, expect, it } from 'vitest';
import { compliantRepo, FixtureRepo } from '../test/fixture-repo.js';
import {
  agentsMd,
  devcontainerNonRoot,
  lastDockerfileUser,
  noEnvCommitted,
  runChecks,
  secretScanHook,
  worktreeConvention,
} from './checks.js';

let repo: FixtureRepo;
afterEach(() => repo?.remove());

describe('a compliant repo', () => {
  it('passes every check', () => {
    repo = compliantRepo();
    const failures = runChecks(repo.root).filter((r) => !r.passed);
    expect(failures).toEqual([]);
  });
});

describe('agents-md', () => {
  it('fails when AGENTS.md is missing', () => {
    repo = new FixtureRepo();
    expect(agentsMd.run(repo.root)).toMatchObject({
      passed: false,
      detail: 'No AGENTS.md at the repo root.',
    });
  });

  it('fails when AGENTS.md is blank', () => {
    repo = new FixtureRepo().write('AGENTS.md', '  \n');
    expect(agentsMd.run(repo.root).passed).toBe(false);
  });
});

describe('secret-scan-hook', () => {
  it('fails when no hook mentions secret-scan', () => {
    repo = new FixtureRepo().write(
      '.githooks/pre-commit',
      '#!/bin/sh\nnpm test\n',
    );
    expect(secretScanHook.run(repo.root).passed).toBe(false);
  });

  it('passes for a pre-commit framework config', () => {
    repo = new FixtureRepo().write(
      '.pre-commit-config.yaml',
      'repos:\n  - id: secret-scan\n',
    );
    expect(secretScanHook.run(repo.root)).toMatchObject({ passed: true });
  });
});

describe('devcontainer-non-root', () => {
  it('fails when there is no devcontainer', () => {
    repo = new FixtureRepo();
    expect(devcontainerNonRoot.run(repo.root).passed).toBe(false);
  });

  it('fails when remoteUser is root', () => {
    repo = new FixtureRepo().write(
      '.devcontainer/devcontainer.json',
      '{ "remoteUser": "root" }',
    );
    expect(devcontainerNonRoot.run(repo.root).passed).toBe(false);
  });

  it('fails when no user is set anywhere, since containers default to root', () => {
    repo = new FixtureRepo()
      .write(
        '.devcontainer/devcontainer.json',
        '{ "build": { "dockerfile": "Dockerfile" } }',
      )
      .write('.devcontainer/Dockerfile', 'FROM node:22\n');
    expect(devcontainerNonRoot.run(repo.root).passed).toBe(false);
  });

  it("uses the Dockerfile's last USER when devcontainer.json sets none", () => {
    repo = new FixtureRepo()
      .write(
        '.devcontainer/devcontainer.json',
        '{ "build": { "dockerfile": "Dockerfile" } }',
      )
      .write(
        '.devcontainer/Dockerfile',
        'FROM node:22\nUSER root\nRUN apt-get update\nUSER node\n',
      );
    expect(devcontainerNonRoot.run(repo.root)).toMatchObject({ passed: true });
  });

  it('keeps URLs inside strings when stripping comments', () => {
    repo = new FixtureRepo().write(
      '.devcontainer/devcontainer.json',
      '{ "image": "https://example.com/img", /* note */ "remoteUser": "dev" }',
    );
    expect(devcontainerNonRoot.run(repo.root)).toMatchObject({ passed: true });
  });

  it('fails on invalid JSON instead of crashing', () => {
    repo = new FixtureRepo().write('.devcontainer/devcontainer.json', '{ nope');
    expect(devcontainerNonRoot.run(repo.root).passed).toBe(false);
  });
});

describe('lastDockerfileUser', () => {
  it('returns undefined with no USER line', () => {
    expect(lastDockerfileUser('FROM node:22\n')).toBeUndefined();
  });
});

describe('no-env-committed', () => {
  it('fails when .env is tracked, even in a subfolder', () => {
    repo = new FixtureRepo()
      .write('apps/api/.env', 'FAKE_KEY=not-a-real-key\n')
      .track('.');
    expect(noEnvCommitted.run(repo.root)).toMatchObject({
      passed: false,
      detail: 'Committed: apps/api/.env.',
    });
  });

  it('fails for .env.local', () => {
    repo = new FixtureRepo().write('.env.local', 'X=1\n').track('.');
    expect(noEnvCommitted.run(repo.root).passed).toBe(false);
  });

  it('ignores an untracked .env', () => {
    repo = new FixtureRepo().write('.env', 'X=1\n');
    expect(noEnvCommitted.run(repo.root).passed).toBe(true);
  });

  it('fails outside a git repository', () => {
    repo = new FixtureRepo({ git: false });
    expect(noEnvCommitted.run(repo.root).passed).toBe(false);
  });
});

describe('worktree-convention', () => {
  it('passes when a doc under docs/ describes it', () => {
    repo = new FixtureRepo().write(
      'docs/agents/parallel.md',
      'Run `git worktree add ../agent-2`.',
    );
    expect(worktreeConvention.run(repo.root)).toMatchObject({
      passed: true,
      detail: 'Documented in docs/agents/parallel.md.',
    });
  });

  it('fails when nothing mentions git worktree', () => {
    repo = new FixtureRepo().write('AGENTS.md', '# Agents\n');
    expect(worktreeConvention.run(repo.root).passed).toBe(false);
  });
});
