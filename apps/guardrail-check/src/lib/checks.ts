import { join } from 'node:path';
import {
  filesIn,
  gitTrackedFiles,
  markdownFiles,
  parseJsonc,
  readIfExists,
} from './fs-utils.js';
import type { Check, CheckResult } from './types.js';

function result(check: Check, passed: boolean, detail: string): CheckResult {
  return { id: check.id, title: check.title, passed, detail };
}

export const agentsMd: Check = {
  id: 'agents-md',
  title: 'AGENTS.md gives agents one entry point',
  run(root) {
    const text = readIfExists(join(root, 'AGENTS.md'));
    if (text === undefined)
      return result(this, false, 'No AGENTS.md at the repo root.');
    if (text.trim() === '') return result(this, false, 'AGENTS.md is empty.');
    return result(this, true, 'AGENTS.md found.');
  },
};

/** Hook locations checked, relative to the repo root. */
export const HOOK_FILES = [
  '.githooks/pre-commit',
  '.githooks/pre-push',
  '.husky/pre-commit',
  '.husky/pre-push',
  '.pre-commit-config.yaml',
];

export const secretScanHook: Check = {
  id: 'secret-scan-hook',
  title: 'A secret scan runs before code leaves the machine',
  run(root) {
    const wired = HOOK_FILES.filter((file) =>
      /secret[-_]scan/.test(readIfExists(join(root, file)) ?? ''),
    );
    return wired.length > 0
      ? result(this, true, `secret-scan is called from ${wired.join(', ')}.`)
      : result(
          this,
          false,
          `No hook calls secret-scan (looked in ${HOOK_FILES.join(', ')}).`,
        );
  },
};

/** The last `USER` instruction in a Dockerfile, or undefined if there is none. */
export function lastDockerfileUser(dockerfile: string): string | undefined {
  const users = [...dockerfile.matchAll(/^\s*USER\s+(\S+)/gim)].map(
    (m) => m[1],
  );
  return users.at(-1);
}

function isRoot(user: string): boolean {
  return (
    user === 'root' ||
    user === '0' ||
    user.startsWith('0:') ||
    user.startsWith('root:')
  );
}

export const devcontainerNonRoot: Check = {
  id: 'devcontainer-non-root',
  title: 'The devcontainer runs as a non-root user',
  run(root) {
    const dir = join(root, '.devcontainer');
    const raw = readIfExists(join(dir, 'devcontainer.json'));
    if (raw === undefined)
      return result(this, false, 'No .devcontainer/devcontainer.json.');

    let config: Record<string, unknown>;
    try {
      config = parseJsonc(raw) as Record<string, unknown>;
    } catch {
      return result(
        this,
        false,
        '.devcontainer/devcontainer.json is not valid JSON.',
      );
    }

    // remoteUser wins over containerUser, which wins over the image's USER.
    for (const key of ['remoteUser', 'containerUser']) {
      const user = config[key];
      if (typeof user === 'string') {
        return isRoot(user)
          ? result(this, false, `${key} is "${user}".`)
          : result(this, true, `${key} is "${user}".`);
      }
    }

    const build = config['build'] as { dockerfile?: string } | undefined;
    const dockerfileName =
      build?.dockerfile ?? (config['dockerFile'] as string | undefined);
    const dockerfile = dockerfileName
      ? readIfExists(join(dir, dockerfileName))
      : undefined;
    const user = dockerfile ? lastDockerfileUser(dockerfile) : undefined;
    if (user === undefined) {
      return result(
        this,
        false,
        'No remoteUser, containerUser or Dockerfile USER set, so it runs as root.',
      );
    }
    return isRoot(user)
      ? result(this, false, `Dockerfile's last USER is "${user}".`)
      : result(this, true, `Dockerfile's last USER is "${user}".`);
  },
};

/** Template files that document variables without holding values. */
const ENV_TEMPLATES = /^\.env\.(example|sample|template)$/;

export const noEnvCommitted: Check = {
  id: 'no-env-committed',
  title: 'No .env file is committed',
  run(root) {
    const tracked = gitTrackedFiles(root);
    if (tracked === undefined)
      return result(
        this,
        false,
        'Not a git repository, so this could not be checked.',
      );
    const envFiles = tracked.filter((path) => {
      const name = path.split('/').at(-1) ?? '';
      return (
        (name === '.env' || name.startsWith('.env.')) &&
        !ENV_TEMPLATES.test(name)
      );
    });
    return envFiles.length > 0
      ? result(this, false, `Committed: ${envFiles.join(', ')}.`)
      : result(this, true, 'No .env files are tracked by git.');
  },
};

export const worktreeConvention: Check = {
  id: 'worktree-convention',
  title: 'One-worktree-per-agent convention is documented',
  run(root) {
    // Look for the actual command, not just the words "git worktree": a plan that says
    // "agents get their own worktree" doesn't tell anyone how to make one.
    const candidates = [
      join(root, 'AGENTS.md'),
      ...markdownFiles(join(root, 'docs')),
      ...filesIn(join(root, 'scripts')),
    ];
    const found = candidates.find((path) =>
      /git worktree add/i.test(readIfExists(path) ?? ''),
    );
    return found
      ? result(this, true, `Documented in ${found.slice(root.length + 1)}.`)
      : result(
          this,
          false,
          'No doc or script in AGENTS.md, docs/ or scripts/ shows how to create one ("git worktree add").',
        );
  },
};

export const ALL_CHECKS: Check[] = [
  agentsMd,
  secretScanHook,
  devcontainerNonRoot,
  noEnvCommitted,
  worktreeConvention,
];

export function runChecks(
  root: string,
  checks: Check[] = ALL_CHECKS,
): CheckResult[] {
  return checks.map((check) => check.run(root));
}
