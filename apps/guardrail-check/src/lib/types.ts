/** The outcome of one guardrail check against one repository. */
export interface CheckResult {
  id: string;
  title: string;
  passed: boolean;
  /** One line a person can act on: what was found, or what is missing. */
  detail: string;
}

/** A check reads the repository at `root` and never modifies it. */
export interface Check {
  id: string;
  title: string;
  run(root: string): CheckResult;
}
