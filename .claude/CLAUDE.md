# Working methodology (per change)

Cross-model, minimal-code, learn-as-you-go. Run the flow for any non-trivial change;
skip it for typos and one-liners.

## Always on (ambient — you never invoke these)
- **ponytail** — minimalism discipline, auto-applies to every coding task (its SessionStart hook flips it on: "PONYTAIL MODE ACTIVE").
- **graphify** — a hook reads the codebase graph before every search, once you've built it (`/graphify`).

## The flow — grill's three acts + compound
| Step | What happens | Tool |
|------|------|------|
| **1. PLAN** (Act 1) | interview locks the plan | `/grill-me-codex` |
| **2. REVIEW** (Act 2) | Codex adversarially reviews the **plan** until APPROVED | ↑ same command (bundled with Act 1) |
| **3. BUILD** (Act 3) | Codex builds → Claude reviews the diff **+ runs the proof test** | `/codex-build` — or self-build\* |
| **4. COMPOUND** | capture the win | append one entry to `docs/learnings.md` |

\* **Self-build** (in Claude) instead of `/codex-build` for: tiny changes (<20 lines), UI/design
(visual iteration), or anything needing Claude's MCP/browser. Then do the review + verify by
hand: `/codex:review` + `/ponytail-review` → `/verify`.

**Small autonomous fixes:** `/auto-fix <n>` — `/auto-issue` minus the Codex loop, for
contained Prototype-territory bugs with a runnable proof. Measurement replaces the
adversarial review; it still stops at the PR.

**UI (cross-cutting):** `/design-shotgun` for variants, `/impeccable` to polish.


## First time in a repo (once, only when it applies)
- UI work here? → `/impeccable init` (writes `PRODUCT.md` / `DESIGN.md`)
- Big/unfamiliar codebase? → `/graphify` (builds the map; then it's automatic)
- Has a database? → generate `schema.dbml` → paste at dbdiagram.io for the ER diagram
- ponytail: nothing — on as soon as it's enabled.

## Prereqs (installed once, machine-wide — not per repo)
- **Codex CLI** authed (`codex login`) — powers grill Act 2/3 and `/codex:*`
- **ponytail** + **codex** plugins cached (enable per repo below)
- **impeccable** (design): Claude plugin or `npx impeccable install`; **design-shotgun**: gstack (global)
- **graphify** (codebase graph): `pip install graphifyy && graphify claude install && graphify codex install` — adds a global PreToolUse hook that no-ops without a `graphify-out/`
- grill skills live in this repo's `.claude/skills/` (copied from the template)

## This repo's tools
Everything in `.claude/settings.json` starts `false` — flip on only what this repo needs.
**One form per tool:** a plugin **or** an `.mcp.json` server, never both (that double-serves).
