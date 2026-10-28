## Agent skills

### Issue tracker

Issues and specs live in this repo's GitHub Issues (`Silvelle/lecture-notes-skill`, via the `gh` CLI). See `docs/agents/issue-tracker.md`.

### Triage labels

Default five-role vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.

### Finishing a ticket

When a ticket's work is done (tests and typecheck pass, `/code-review` findings handled):

1. Commit with `Closes #<n>` in the message body so GitHub closes the issue automatically. Use `Refs #<n>` only for partial work.
2. Never use arrows (`→`, `->`) in commit messages.
3. Push `main` right away; the issue closes when the commit lands. Then check CI (`gh run watch`) and fix any failure in a follow-up commit.
