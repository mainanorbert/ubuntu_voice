---
name: peacetech-commit-prep
description: Prepare Ubuntu Voice changes for commit and optional push. Use when the user asks to commit, create a commit message, prepare a PR-ready diff, run final checks, or push changes in the ubuntu_voice project.
---

# PeaceTech Commit Prep

Prepare changes for a clean commit using the Ubuntu Voice project rules. Commit or push only when the user explicitly asks.

## Guardrails

- Never commit or push `.env`, `.env.local`, secrets, tokens, passwords, or generated files that should stay ignored.
- Never include secret values in summaries, commit messages, logs, or final responses.
- Never revert unrelated user changes.
- Do not push unless the user explicitly asks to push.
- If the user asks for a commit but not a push, stop after the commit and report the commit hash.

## Workflow

1. Read the nearest `AGENTS.md`.
2. Inspect `git status --short`.
3. Inspect staged and unstaged changes with `git diff --stat`, `git diff --cached --stat`, and targeted diffs.
4. Identify the smallest relevant verification commands:
   - Backend: `cd backend && uv run pytest -q`
   - Frontend: `cd frontend && npm run lint`, `npm run typecheck`, and `npm run build`
5. Run focused checks first for narrow changes; run full checks for multi-file or cross-cutting changes.
6. Summarize the diff and verification outcome.
7. Create a concise imperative commit message that reflects the actual diff.
8. Commit only the intended files.

## Push Workflow

Only push when the user explicitly asks.

Before pushing:

1. Confirm the current branch with `git branch --show-current`.
2. Confirm the remote with `git remote -v`.
3. Confirm the commit exists with `git log -1 --oneline`.
4. Push the current branch to the intended remote.

## Output Format

Return:

1. Files committed.
2. Verification commands run and their result.
3. Commit hash and message.
4. Push result, only if a push was requested.
5. Any skipped checks with the reason.
