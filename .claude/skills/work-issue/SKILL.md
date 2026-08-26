---
name: work-issue
description: Work one GitHub issue end-to-end — issue read → board → worktree → plan (Gate 1) → build → review → lesson → PR → STOP for merge. Worktree-native **by default** — every issue runs in its own `.worktrees/<branch>` so parallel sessions never collide. e.g. "/work-issue 4".
---

# Work Issue

Own the **GitHub-issue lifecycle** around this repo's build flow (grill → build → review →
compound). Create the **worktree up front** (Step 3), then delegate the build to
`/codex-build` or self-build, working *inside that worktree* — never `git checkout -b` in
the primary tree, which dirties `main`.

Read `CLAUDE.md` for the rules this enforces: the git blast-radius table, the two-speed
testing dial, security non-negotiables, and the Postgres/Supabase migration rules.

## Args
The issue number (e.g. `4`). If omitted, ask which issue.

## Who you are explaining to — applies to EVERY reply, not just the lesson

**The baseline, stated by the reviewer directly:** knows basic SQL and `JOIN`. Does **not**
know what a *policy* is, what a *GRANT* is, or any database security strategy.

They also do **not** hold `docs/schema.dbml` or ADR-001 in working memory. The design lives in
documents, not in their head, so anything phrased in schema vocabulary is unanswerable.

This governs **chat replies, plan summaries, PR descriptions and lessons alike.** It is not a
documentation rule; it is how you write.

### The test, which is not a word list

This section used to list the terms to define — policy, GRANT, RLS, `security definer`, trigger,
SQLSTATE, transaction. **The list made things worse: it reads as complete, so you satisfy it and
stop.** In #34 every term on it was defined, and these went undefined in the same conversation:
token · hash · signed · server-side · fixture · foreign key · index · idempotent · race ·
SIGPIPE · exit code. The reviewer had to ask three separate times.

So the test is:

> **Would they have to look this up, or ask someone, to follow my sentence?**
> If yes, it gets one plain sentence before you use it — or you rewrite the sentence.

Applied honestly it catches terms that feel too basic to bother with. Define them anyway; it
costs a clause. Once per conversation is enough.

### Never let an issue number do the work of an explanation

`#33`, `#6`, `#37` are pointers, not meaning. A reply that says *"moved to #33"* or
*"that is #37's shape"* cannot be followed without leaving it and opening GitHub, and the
reviewer named this directly: **"Explain it easily not referencing by #number."**

Name the thing, then cite the number in parentheses if it is useful:

| Instead of | Write |
|---|---|
| "the viewer assertion moved to #6" | "that test needs the player tables, which don't exist yet (tracked in #6)" |
| "this is #37's shape" | "the same trap as the `REVOKE` that printed success and changed nothing (#37)" |
| "depends on 2b and 2c" | "needs the login screen and the invitation-link page, neither built yet" |

Same rule for file paths and identifiers. `ADR-001 §9` means nothing on its own; *"the four
jobs allowed to use the key that bypasses row security (ADR-001 §9)"* does.

### The shape of any explanation

1. **Frame the problem before the answer.** What is actually at stake, in one or two lines,
   before any mechanism. "Two clubs share one table and must not see each other's rows" comes
   before the word *policy* ever appears.
2. **Define each load-bearing primitive at first use** — one short paragraph, from basic SQL
   upward, by the test above.
3. **Ground it in this repo's own tables** — real names (Boca, Arsenal, Martín), real columns,
   2–3 example rows. Never `foo`/`bar`, never an abstract `entity`.
4. **Walk one concrete failure.** "Martín runs *this query* and gets back *these rows*." A
   named consequence teaches; "this could leak data" does not.
5. **Then** the answer, decision, or options — shortest first.

**Consequence before mechanism, every time.** In #34 the lookup bug was first reported as
*"PostgREST `ilike` treats `_` as a wildcard"* — true, and the wrong opening. The sentence that
mattered was *"the script told you someone had already joined when they never had, created
nothing, and exited 0."* Lead with what happened to a person; the mechanism is the second
paragraph, for whoever wants it.

### Show it running rather than describing it

A definition explains; a demonstration convinces, and it is usually three lines of shell. In
#34, *hash* and *token* took three prose attempts and then landed immediately on this:

```
token                        Z2ROQmRyYVBqSVJmS0RfUEJRcDJRc3JqVGxzVzNzOFo
its fingerprint              b764e7a4f0d85674d3b50519203e2fc0eae134a93f01e403912beccb408f0961
same token again             b764e7a4…0961   ← identical, so we recognise him
ONE character changed        7d66e9fc…6bf3   ← completely different
```

Reach for this whenever a concept has observable behaviour: run the query and paste the rows,
run the two commands and paste both outputs, break it on purpose and paste the error. **Real
output outranks any sentence you could write about it**, and it is the same discipline this repo
applies to claims about the database — measure, do not assert.

### When they state their own understanding, answer that first

Twice in #34 the reviewer wrote out their mental model and asked *"is this right?"* — and a
direct verdict on it was worth more than any explanation, because it told them which part of
their picture to keep.

So when a reply arrives containing "so to be clear…" or "is this right?":

1. **Answer right / wrong / partly, in the first line.** Not after three paragraphs of context.
2. **Name which specific part is off**, and say what is true instead.
3. **Confirm the parts that are correct explicitly** — silence on those reads as disagreement.

Their model being *mostly* right is the common case, and the one sentence that repairs it is the
whole value of the reply.

### What to cut

Reasoning trail, alternatives you already rejected, and round-by-round narration. Lead with
the conclusion and the one fact that decides it. Detail goes *after*, or in the lesson.

A three-row table plus one worked failure beats four paragraphs of prose. If a reply cannot be
followed without opening another file, it is not finished.

### Asking them to decide

Same shape, ending in the options. Give a recommendation and say why in one line.

**An option must be readable without the jargon that distinguishes it from the others.** Check
each label against: *could they choose this without knowing a term I have not defined?* A
question that fails this is not hard, it is unanswerable — and #34's first one was refused on
exactly those grounds.

| Unanswerable | Answerable |
|---|---|
| "`security definer` RPC vs `psql` over `DATABASE_URL`" | "one command the database runs all-or-nothing, vs four requests that can half-finish" |
| "partial unique index on `(org_id, lower(email))`" | "let the database refuse a second live invitation for the same person" |
| "`--verify` runs the isolation harness" | "after applying, re-run the isolation harness against the real database" |

**Every option carries its cost** — not "cheaper", but *what specifically goes wrong if you pick
this*. A three-option question where only one has a stated downside has already made the choice.

**Push-back is information you were missing, not a request to re-explain.** Across #31 and #34
the reviewer overturned a recommendation five times and was right five times. Twice the
correction was already sitting in the repo: once a "gap" turned out to be specified in a filed
issue, and once the sequence being invented in chat was already on the board. So when push-back
arrives, **go and check before defending.**

## Write the lesson as you go — not at the end

`PLAN.md` and `PLAN-REVIEW-LOG.md` are **gitignored**. Reconstructing a lesson from them at
Step 8 means writing from a scratch file that will not survive `git worktree remove`, and the
detail that makes a lesson worth reading — *which* round found *what*, and why the previous
fix was wrong — is exactly what fades first.

So **create `docs/lessons/<issue>-<slug>.md` at Step 4** and append to it continuously. It is a
tracked file from the first commit.

**After every round** — each grill round, each Codex review round, each build/fix round, and
each time verification finds something — append two things:

1. **Concepts** — any idea a reader would need in order to follow what happened. One line
   each, under a running `## Concepts in play` list. If a concept is not yet in
   `docs/lessons/00-deployment-101.md`, note it as `(NEW → 00)`; it gets written into the
   index in this same PR.
2. **A problem → solution entry** — under a running `## Rounds` section:

   ```markdown
   ### Round <n> — <one-line title>
   **Problem:** what was actually wrong, concretely.
   **Why it was not obvious:** what made it read as correct.
   **Fix:** what changed.
   **Cost:** rounds spent, what a human had to do, what was thrown away.
   ```

**Record the wrong turns at the moment they are wrong**, including your own — a recommendation
the user overturned, a fix that introduced a new defect, a rationale that did not survive
review. Those are the entries with teaching in them, and they are the first thing lost if you
wait. Never sand them down later.

At Step 8 the lesson is then **shaped and finished**, not written: turn the running `## Rounds`
log into narrative sections, keep the honest cost, add *Try this yourself*, and delete the
scaffolding headings. The raw log is the input, not the output.

## Steps

1. **Read the issue.** `gh issue view <n>` (+ comments). Restate goal + acceptance criteria
   in one line. Read-only recon is fine on any branch — but **edit nothing** until the
   worktree exists (Step 3).
2. **Track.** Move the issue to **In Progress** on Project **#8**. If the issue names an
   epic ("Part of #\<epic\>") but is not yet a **native sub-issue** of it, add the link now
   (`gh api repos/{owner}/{repo}/issues/<epic>/sub_issues -F sub_issue_id=<id>` — see
   `CLAUDE.md` §Issue tracking for the exact form). The epic's done-ratio is computed only
   from native sub-issues; a body mention keeps humans informed and the progress bar wrong.
3. **Worktree first (default).** Off the latest `main`, *before any edit*:
   ```bash
   git fetch origin
   git worktree add .worktrees/<branch> -b <branch> origin/main   # e.g. feat/org-tenancy
   ```
   From here on **every** change goes in `.worktrees/<branch>/…` via absolute paths; run git
   as `git -C .worktrees/<branch> …`. Skip the worktree only for a throwaway, no-file-change
   task.
4. **Plan — Gate 1.** `/grill-me-codex` for anything non-trivial: it interviews you to lock
   the plan (Act 1), then Codex adversarially reviews it until APPROVED (Act 2). Tiny chores
   get a short inline plan instead. **Show the plan and wait for approval before any code.**
   - Touching tenancy, auth, RLS, schema or migrations? Gate 1 is **mandatory** — never
     improvise those. The settled answers live in `docs/decisions/`.
   - **Create `docs/lessons/<issue>-<slug>.md` now**, not at Step 8 — see *Write the lesson
     as you go* below.
5. **Build.** `/codex-build` with the frozen plan, *or* self-build in Claude when it is
   tiny (<20 lines), visual/UI iteration, or needs MCP/browser.
   - Codex writes files and **runs no git** — the dirty tree is the review artifact.
   - Right-size rigor per the dial in `docs/ROADMAP.md`: **Prototype** for ordinary wave-1
     work (typecheck + lint, no test gate); **Harden** for anything touching tenancy, auth,
     RLS or secrets (tenant-isolation test + `/security-review`, non-negotiable).
6. **Verify.** Run `pnpm quality` **before reading the diff** — otherwise you review
   formatting noise instead of logic. Then `/codex:review` + `/ponytail-review`.
   Add `/security-review` for anything in Harden mode.
7. **Capture.** Append one entry to `docs/learnings.md` for anything non-obvious. Keep it
   short: what bit us, the fix, the rule.

   **Do not end the issue by filing a pile of follow-ups.** See *Finishing beats filing*
   below — the bar for a new issue is that the work would need its own adversarial review,
   and most things that feel like follow-ups are either doable now or are decisions rather
   than work.
8. **Teach — finish the lesson** you have been appending to since Step 4 (see *Write the
   lesson as you go* above). Every issue ships a teaching artifact in
   `docs/lessons/<issue>-<slug>.md`, **committed before the PR is merged.** It is written
   *teacher → student*: the reader is a competent developer who was not in the room and is
   learning how full-stack work actually goes when an AI is doing the building.

   **It is not a changelog and not a summary of the diff.** A diff shows *what* changed; the
   lesson explains *why that was the right change and how we knew*. Cover:
   - **The question the issue was really asking**, and whether its premise survived contact.
     An issue whose stated scope turned out to be impossible is the most valuable lesson
     available — write it up rather than quietly routing around it.
   - **The decision and its alternatives**, including the ones rejected and why. A decision
     with no visible alternatives teaches nothing.
   - **What went wrong.** Bugs that type-checked and passed lint, things only runtime caught,
     wrong turns and dead ends. **Never sand this down** — the failures carry the teaching,
     and a lesson where everything worked first time is the least useful thing you can write.
   - **The transferable rule**, stated so it applies beyond this repo.

   Keep it honest about cost: rounds spent, time lost, what a human had to do by hand.

   **Do not duplicate `docs/learnings.md`.** That file is terse operational memory — one trap,
   one rule, addressed to whoever hits it next. A lesson is narrative and explains reasoning
   to someone learning the craft. Cross-link rather than restate.

   **Required structure:**
   - **TL;DR** — **first thing in the file**, immediately under the title line, before
     *Essentials*. Five to eight lines, readable in twenty seconds, and complete on its own:
     someone who reads only this should come away with the right conclusion, not a teaser that
     forces them to read on.

     Cover, in this order: **what was asked**, **what turned out to be true** (say so plainly
     when the premise was wrong), **what shipped**, and **the one rule worth keeping**. Prefer a
     short bullet list; a table is fine when the lesson turns on a before/after.

     Two things it must not become. It is **not an abstract** — no "this lesson explores".
     Write the findings themselves, with the real numbers and names. And it is **not a place to
     launder the failures**: if the lesson's teaching is that we got it wrong, the TL;DR says we
     got it wrong. A summary that reads like a success while the body describes three failed
     rounds is the one shape that makes the whole document untrustworthy.

     Write it **last**, once the body exists — a TL;DR drafted first summarises the lesson you
     expected to write rather than the one you wrote.
   - **Essentials** — the reader must be able to follow the whole lesson **without leaving
     it.** This is the section they asked for explicitly: *"for every PR I want to learn the
     essentials to understand the technical problems."*

     **Write to this baseline, every time:** basic SQL and `JOIN`, and nothing else.
     Specifically **not** assumed: policy, GRANT, RLS, `security definer`, trigger, SQLSTATE,
     transaction/savepoint, multi-tenancy. If a term is load-bearing and undefined, the lesson
     is unreadable no matter how good the prose is.

     Each concept gets: **what it is** in plain language, **why it bites** (the failure it
     causes), a **concrete example from this repo's own tables**, and a `→` link to the full
     treatment in `00`. Roughly a short paragraph each — a one-line restatement of the heading
     is not a recap, it is a table of contents.

     Anchor each one to the section of *this* lesson where it pays off (`§2`, `§3`), so the
     reader knows why they are being told it.

     `00` is the **living concept index**: if this lesson depends on a concept `00` does not
     cover, add it to `00` **in the same PR** — the same rule as a scope change shipping its
     roadmap edit. Check `00` actually covers the *primitives*, not just the clever bits: a
     concept explaining "permissions have a grain" is useless above a reader who has never been
     told what a permission is.

## The handbook — `docs/lessons/00-deployment-101.md`

**`00` is a book, not a file, and it is going to get much bigger.** Step 2 of the roadmap is
barely started. Treat every PR as writing one more page of it, and keep the structure so it
never needs another reorganisation.

### Its shape, which does not change

```
Front matter        what it is, who it is for, how to read it
# Index             LINKS ONLY — no prose, no content, nothing that can rot
  ## Essentials       every concept, grouped by Part
  ## Problems         every real failure: PR · date · what broke · the concept
# Part One…Four     the concepts themselves
# Where the failures live   one row per lesson: PR · date · what it teaches
```

The **Index carries no content**. It is navigation. Anything worth reading lives in a concept
or in a lesson, once.

**The stories are never in `00`.** They live in their lesson. `00` links to them. An earlier
version kept condensed copies of Lesson 20's failures inside `00`, which meant two versions of
one story and two places to fix a mistake.

### What every PR adds

| Where | What |
|---|---|
| `## Essentials` | each new concept, under the Part it belongs to |
| `## Problems` | one row per real failure: **PR number · date** · what went wrong · the concept |
| the concept body | a **`Where it bit us:`** line — `#PR · date — what it cost`, linking the lesson section |
| `# Where the failures live` | a row for the new lesson: PR · date · what it teaches |

**The PR number and date are the spine.** They are what connect a concept to the problems that
taught it and to the lesson that tells the story, in both directions. A concept with no
`Where it bit us:` line is either untested theory or a missing link — decide which.

### Navigation is required, in both directions

- every **Part heading** → `[↑ Index](#index)`
- every **concept** ends with `[↑ Index](#index) · [← previous](#…) · [next →](#…)`
- every **lesson** opens its Essentials with
  `[↑ The handbook](./00-deployment-101.md#index) · [all lessons](./README.md)`
- every **lesson** ends with the same, plus
  `[the problems index](./00-deployment-101.md#problems)`

A reader must be able to go index → concept → the failure that taught it → back, without
scrolling or guessing.

### Rules that came from getting this wrong

- **Never number a heading you intend to link to.** The number lands in the anchor, so
  inserting one concept silently breaks every link to the ones after it — in markdown that
  still looks correct. Reference by name.
- A concept belongs to **exactly one** Part. If it fits two, the Part boundaries are wrong.
- **Verify against the rendered HTML, never the markdown.** A link to a heading that does not
  exist produces no error anywhere:
  ```bash
  pnpm lessons:render
  for a in $(grep -o '](#[a-z0-9-]*)' docs/lessons/00-deployment-101.md | tr -d '](#)' | sort -u); do
    grep -q "id=\"$a\"" docs/lessons/html/00-deployment-101.html || echo "DEAD #$a"
  done
  ```
  The renderer assigns ids to `h1`–`h4`. If you introduce a deeper heading and link to it,
  extend `scripts/render-lessons.mjs` rather than avoiding the link.
- **Re-publish every page whose anchors or links changed**, not only the new lesson — and pass
  the canonical URL from `docs/lessons/artifacts.json`, because publishing from a different
  worktree path otherwise forks the page to a new URL.

     **The split that avoids duplication:** `00` holds the canonical, general explanation; the
     lesson's recap says what the concept *meant here*. They say different things, so a wrong
     concept still has exactly one place to fix.
   - **The body** — as described above.
   - **Try this yourself** — two to four things a student can run or break in a few minutes,
     each producing a symptom the lesson describes. Reading about a failure is much weaker
     than causing one. Concrete commands, not "consider exploring".
   - **`docs/lessons/README.md`** — add the lesson to the index table with its one-line hook.

   **Diagrams are ```mermaid fences in the markdown.** GitHub renders them in the repo and the
   published page renders them too, so a diagram never exists in only one place. Do not
   hand-author SVG into the HTML — it is generated output.

   Then render and publish:
   ```bash
   pnpm lessons:render        # docs/lessons/*.md -> docs/lessons/html/*.html
   ```
   Publish the generated HTML with the **Artifact** tool for a shareable URL. Re-publish the
   same path when revised — same path, same URL.

   **The markdown is the only source.** The HTML is generated and **gitignored**; the Artifact
   is the hosted copy. Never edit the HTML — the renderer overwrites it, and an edit there is
   a change that exists in no tracked file.
9. **Sync with `main`.** Before the PR, absorb anything that landed while you worked:
   `git fetch origin && git merge origin/main` — **merge, not rebase**: `main` is
   squash-merged and never force-pushed, so merge is safe and rebase just invites conflicts.
   Resolve, then re-run the verify gates so the *merged* result is green. Skip if `main`
   hasn't moved.
10. **PR + STOP.** Open the PR (`gh pr create`); the body must contain `Closes #<n>` plus the
   review summary. If this is a scope change, the `docs/ROADMAP.md` edit ships **in this same
   PR** — as does the lesson from Step 8. Then **STOP**: tell the reviewer `"PR open: <url> — waiting for merge approval"`.
   **Do not merge** — pushing to `main` is a production deploy and is human-only.

## On merge approval
When the user says "merge `<branch>`": if `main` moved since the PR opened, sync once more
(`git fetch origin && git merge origin/main`, resolve, re-verify, push). Then merge, **apply the
migration if the PR had one** (below), move the issue to **Done** on Project #8, confirm
`Closes #<n>` auto-closed it, and clean up.

### `--delete-branch` cannot work from a worktree, and its error reads like a failed merge

**Never `gh pr merge --squash --delete-branch` here.** This skill is worktree-native by default, so
the branch being merged is checked out in `.worktrees/<branch>` — and `--delete-branch` makes `gh`
do *local* git work after the API call: check out the base branch, then delete the local branch.
Both are impossible from a worktree, because `main` is checked out in the primary tree and the
branch is checked out in this one. Measured:

```
$ gh pr merge 101 --squash --delete-branch
failed to run git: fatal: 'main' is already used by worktree at '/Users/…/scouting.cronolix'
$ gh pr view 101 --json state,mergedAt
state=MERGED  mergedAt=2026-08-17T08:54:52Z          ← it merged. The error is post-merge cleanup.
```

**That is the hazard, not the tidiness.** The command exits non-zero with a `fatal:` from git, which
reads as "the merge did not happen" — and the wrong response to that is to retry it. **Check
`gh pr view <n> --json state,mergedAt` before believing any error from a merge command.**

Split it instead. Four steps, each with an obvious failure mode:

```bash
gh pr merge <n> --squash                       # API only. No local git, so no worktree conflict.
# … the migration step below, then the board and the issue …
git -C <primary-repo> worktree remove .worktrees/<branch>
git -C <primary-repo> push origin --delete <branch>
git -C <primary-repo> branch -D <branch>
```

Two things about that last line. It must come **after** `worktree remove`, because git refuses to
delete a branch that is checked out anywhere. And it is **`-D`, not `-d`** — a squash merge writes a
*new* commit, so the branch's own commits are not ancestors of `main` and `git branch -d` refuses
with "not fully merged". Nothing is lost: the content is on `main` under a different sha.

**Why this is a corrected instruction and not a script.** `scripts/db-push.sh` exists because
applying a wrong migration is unrecoverable, so that step is worth wrapping in a command that
cannot be typed wrong. This failure is the opposite: benign, loud, and two commands to recover
from. Wrapping it would put the merge procedure in two places — the script and this section — and
two descriptions of one procedure is the drift `CLAUDE.md` warns about for `AGENTS.md`. **Script the
irreversible; correct the prose for the merely annoying.**

### Applying the migration is part of the merge — never a thing anyone remembers

**Merging deploys the Worker. It does not touch the database.** So a migration PR that merges
cleanly leaves production running new code against an old schema, silently, until the schema
is pushed. That gap closes here, in the same breath as the merge, or it does not reliably
close at all.

**"merge `<branch>`" is the gate.** It is a human sentence authorising this change to reach
production, and the schema is part of that change. Do not ask a second time.

This is **not** the CI automation in [#41](https://github.com/ipastore/scouting.cronolix/issues/41).
That still needs GitHub environment protection rules and is still blocked. What changed is only
*who types the command* after a person has already approved.

**Four steps, in order, immediately after `gh pr merge`:**

```bash
# 1. Did this PR touch the schema at all?
git diff --name-only HEAD~1 HEAD -- supabase/migrations/
```

Empty → **skip the rest and say so explicitly** ("no migrations in this PR; nothing to apply").
Silence reads as "forgot", which is the failure this section exists to remove.

```bash
# 2. What would apply. Touches nothing, exits 0.
bash scripts/db-push.sh --dry-run
```

```
# 3. Compare `pending` against the files step 1 listed.
```

They must match. **Anything pending that this PR did not add means the database and `main` have
desynchronised — stop, report both lists, apply nothing.** That state has a known cause
(`docs/learnings.md`, 2026-08-08: hand-applying a branch's migrations to staging puts it ahead
of `main` and breaks every sibling branch), and guessing past it is how a half-applied schema
happens.

```bash
# 4. Apply, then prove it against the real database.
bash scripts/db-push.sh --verify --yes
```

Report the harness result — assertion count and pass/fail — not just "applied".

**`--yes` is mandatory here, and is not a shortcut.** `scripts/db-push.sh:141` confirms with
`read -r reply </dev/tty`, and an agent shell has no controlling terminal:

```
$ read -r reply </dev/tty
bash: /dev/tty: Device not configured        # read exits 1, reply stays empty
```

The empty reply falls through to `*)`, the script prints `aborted.` and exits 1 **having applied
nothing.** It fails closed, correctly — but it also means the bare command cannot run from a
session like this one at all. That measured fact, not a policy about trust, is why this step was
manual for so long.

**Production only.** Never `--staging` by hand: CI already applies the branch's migrations to
staging on the pull request, and doing it again from a branch puts staging *ahead* of `main`,
after which `supabase db push` refuses to run on every sibling branch with an error that names
the migrations rather than the cause.

**If `--verify` fails, say so immediately and stop.** Migrations have no undo: an invalid one
rolls back harmlessly, a *valid but wrong* one has already applied cleanly and done the wrong
thing. The fix is forward, in a new migration, and it is the reviewer's call — not a retry.

### The one case where the migration goes in *before* the merge

Merging is the deploy, so ordering follows `CLAUDE.md`'s expand-before / contract-after rule:

| The PR contains | Correct order | If you merge first |
|---|---|---|
| an **additive** migration only (2a) | merge → apply → *then* merge the app PR (2b) | fine — no code depends on it yet |
| **destructive** changes (drop, rename) | merge → apply | fine — the old code is already gone |
| an additive migration **and** the code that queries it | ⚠ **do not merge** | every request 500s on a column that does not exist |

That third row is a **split defect, not a sequencing puzzle.** The repo separates `supabase/`
and `web/` into different issues precisely so it cannot arise. If a PR reaches merge approval
carrying both, stop before merging, say which files are on each side, and propose splitting it —
do not reach for a workaround like applying from the feature branch, which leaves production
carrying a migration that is not on `main` if the PR is ever abandoned.

## Parallel work (worktrees)
Default, not opt-in: each `/work-issue <n>` runs in its **own** `.worktrees/<branch>`, so
several can run in **separate Claude sessions** at once. Worktrees share one `.git` but have
independent working directories and branches — edits on one never touch another's files
until merged through `main`.

They isolate *files*, not *logic*: two issues editing the same files still collide at the
second PR. So parallelize issues touching **different areas**, and sync the second branch
with `main` (Step 9) after the first merges.

## Finishing beats filing

**The bar for opening a new issue is that the work would have to go back through the full
loop — plan, adversarial review, build, verify** (owner decision, 2026-08-11). Nothing below
that bar earns an issue. Filing it does not defer the work, it buries it: a backlog nobody
will prioritise is a to-do list that decays, and a repo that opens three issues per PR never
finishes anything.

There are **three** outcomes, and the middle one is the one that gets forgotten:

| Outcome | When | Where it goes |
|---|---|---|
| **Do it now** | the default, and far wider than it feels | this PR |
| **Record the decision** | you decided *not* to build something | `docs/ROADMAP.md` — **no issue** |
| **File an issue** | it genuinely needs its own adversarial review | the board |

The middle row is not a weaker form of filing. **Deciding not to build something is not
unfinished work**, so it has no status and does not belong on the board. `CLAUDE.md` puts
scope and sequence in the roadmap and status on the board — a decision is scope. Write it
there with its reasoning, so nobody reopens the argument, and file nothing.

Meeting the bar, in practice: it needs a decision already settled in an ADR or one the human
wrote into an issue comment; it lands in **Harden territory** (tenancy, auth, RLS, schema,
migrations); or it is a genuine **product** fork where two reasonable answers ship materially
different behaviour.

**Re-estimate before you file.** Measured, from #70/#64: two follow-ups were queued at plan
time. "Reap superseded objects" was scoped as a background sweep and turned out to be a single
conditional delete — the route already knew the path it was replacing, because create-only
uploads mean a replacement can never overwrite its predecessor. It shipped in the same PR in
minutes. "In-app org-logo editor" was never pending work at all: it was a deliberate decision
to leave `organizations` with no write policy, and belonged in the roadmap. Both would have
become permanent backlog. The estimate that justifies filing is usually the estimate you have
not checked.

**When you do file, it is a Stop condition, not a footnote.** Do not work around the thing and
present the result as done. Label it (type + wave), link it `Part of #<epic>` **and** as a
native sub-issue, reference it from the PR ("found while doing #\<n\> → filed #\<m\>"), and if
the original issue cannot be finished without it, say so plainly and stop.
