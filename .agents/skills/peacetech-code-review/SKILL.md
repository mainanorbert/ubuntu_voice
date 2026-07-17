---
name: peacetech-code-review
description: Review Ubuntu Voice backend changes before a commit, pull request, merge, or handoff. Use for code-review requests, broad diffs, privacy-first PeaceTech checks, RAG safety checks, logging checks, and verification planning in the ubuntu_voice project.
---

# PeaceTech Code Review

Review changes in the Ubuntu Voice project with a code-review stance: findings first, ordered by severity, with concrete file and line references where possible.

## Workflow

1. Read the nearest `AGENTS.md` before reviewing.
2. Inspect repository state with `git status --short`.
3. Inspect staged and unstaged changed files with `git diff --stat`, `git diff --cached --stat`, and targeted diffs.
4. Prioritize bugs, regressions, privacy risks, unsafe AI behavior, missing tests, and project-rule violations.
5. Keep unrelated user changes intact; do not revert or rewrite unrelated work.

## Review Checklist

- Verify no `.env`, `.env.local`, secret, token, password, or credential values are printed, summarized, logged, committed, or exposed.
- Verify failed database connections are logged at `CRITICAL` level.
- Verify logs avoid PII such as emails, passwords, and sensitive conflict-related details.
- Verify RAG or AI answers stay grounded in retrieved documents and preserve source citations where the UI or API supports citations.
- Verify medium or complex functions/classes have docstrings; simple functions should have a one-line comment when helpful.
- Verify backend changes have relevant tests or a clear reason tests were not run.
- Verify frontend changes have relevant lint, typecheck, build, or focused UI checks when applicable.

## Output Format

Return:

1. Findings: severity, file/line, issue, and suggested fix.
2. Open questions or assumptions.
3. Brief change summary only after findings.
4. Verification commands run or recommended.

If no issues are found, say that clearly and mention any residual test gaps.