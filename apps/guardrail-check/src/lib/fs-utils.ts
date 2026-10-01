import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

export function readIfExists(path: string): string | undefined {
  return existsSync(path) && statSync(path).isFile()
    ? readFileSync(path, 'utf8')
    : undefined;
}

/** Every `.md` file under `dir`, recursively. Returns [] if `dir` is missing. */
export function markdownFiles(dir: string): string[] {
  if (!existsSync(dir)) return [];
  return readdirSync(dir, { recursive: true, encoding: 'utf8' })
    .filter((name) => name.endsWith('.md'))
    .map((name) => join(dir, name));
}

/** The files directly inside `dir` (not subfolders). Returns [] if `dir` is missing. */
export function filesIn(dir: string): string[] {
  if (!existsSync(dir)) return [];
  return readdirSync(dir)
    .map((name) => join(dir, name))
    .filter((path) => statSync(path).isFile());
}

/** Files tracked by git, or undefined if `root` isn't a git repository. */
export function gitTrackedFiles(root: string): string[] | undefined {
  try {
    const out = execFileSync('git', ['ls-files', '-z'], {
      cwd: root,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    });
    return out.split('\0').filter(Boolean);
  } catch {
    return undefined;
  }
}

/**
 * Parse JSON with comments and trailing commas (the "JSONC" that
 * devcontainer.json allows). Comment markers inside strings are kept.
 */
export function parseJsonc(text: string): unknown {
  let out = '';
  let inString = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    const next = text[i + 1];
    if (inString) {
      out += c;
      if (c === '\\') out += text[++i] ?? '';
      else if (c === '"') inString = false;
    } else if (c === '"') {
      inString = true;
      out += c;
    } else if (c === '/' && next === '/') {
      while (i < text.length && text[i] !== '\n') i++;
      out += '\n';
    } else if (c === '/' && next === '*') {
      i = text.indexOf('*/', i + 2);
      if (i === -1) throw new SyntaxError('Unterminated block comment');
      i++;
    } else {
      out += c;
    }
  }
  return JSON.parse(out.replace(/,(\s*[}\]])/g, '$1'));
}
