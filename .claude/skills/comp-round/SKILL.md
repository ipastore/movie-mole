---
name: comp-round
description: Generate impeccable design comps locally through Codex CLI's built-in gpt-image-2 tool, anchored on a screenshot of a real product surface, with no image API key and no per-image cost. Use when the user says "/comp-round", "comps", "generate the mockups", "decision board", when impeccable's new-work flow reaches a comp slot or a comp-led build, or whenever `generate-image.mjs` reports OPENAI_API_KEY is not set — that message means the API path is dead, not that comps are impossible. Also use to regenerate a single card's comp after a re-roll. NOT for screenshotting a built page (that is Playwright), NOT for reviewing a finished build (that is impeccable's finish reviewer).
---

# Comp-Round — Codex generates, anchored on real pixels

Impeccable's comp-led build wants a full-fidelity mockup per direction *before* any code.
Its own generator needs `OPENAI_API_KEY`, which this machine does not have. **Codex CLI does
it instead, free, on the ChatGPT subscription**, through a built-in `image_gen` tool.

That message — `generate-image: OPENAI_API_KEY is not set; use the harness-native image tool
instead` — is the pointer to this skill, not a dead end. Do not read it as "no comps possible"
and fall back to code-led. That mistake was made once already.

## The one command

Prompt on **stdin**, reference image via `-i`, sandbox `workspace-write`:

```bash
cat prompt.txt | codex exec -s workspace-write -i .impeccable/ref/<reference>.png
```

Measured on codex-cli 0.144.1:

| | |
|---|---|
| Feature flag | `image_generation` — `stable`, **already true**. Nothing to enable. |
| Auth | ChatGPT OAuth. `codex login` **without** entering an API key — entering one flips the account to paid per-image billing. |
| Output | 1536×1024 landscape PNG (3:2) |
| Where it lands | Codex writes to `~/.codex/generated_images/<session>/` and copies to the path your prompt names, so **name the destination path in the prompt** |
| Sandbox | `-s workspace-write` is sufficient. Do **not** use `--dangerously-bypass-approvals-and-sandbox`; blog posts recommend it and it is not needed. |
| Cost | ~30–90k tokens per image |

Why it is not a CLI flag: `codex exec --help` shows only `-i/--image`, which is *input*.
Generation is a **tool the model calls**, so it never appears in `--help`. Checking the help
text and concluding Codex cannot generate images is the specific wrong turn to avoid.

## Rules that decide whether the comp is usable

**1. Always pass a reference image.** `-i <screenshot of a real surface of this product>`.
A prose paraphrase of a design system drifts; a pixel reference does not. Capture one with
Playwright into `.impeccable/ref/` first. If the dev server needs env, this repo's
`.env.local` lives at the **repo root**, not in `web/`.

**2. Name `gpt-image-2` in the prompt.** Left unnamed, quality drops.

**3. Lead with structure, then name exact hex values and type character.** "Composed as one
full-bleed ledger sheet, no hero card" beats any adjective. Give literal hexes — the comp is
a picture, not code, so token names mean nothing to it.

**4. One shared set of synthetic facts across every card in a round.** Same club, same player,
same figures. Different content per card compares three products, not three compositions.

**5. Generate cards in parallel, in the user's reading order**, lead card first — a re-roll
should waste the least-read card. Run each as its own background `codex exec`.

**6. Serve the decision board before generating.** The board shimmer-waits on empty comp
slots by design, so the user can start reading while images land.

## Always verify the file is *new*, because Codex will hand you an old one

Measured, on the very first three-card round: one run wrote a comp that was **byte-identical to
an unrelated image generated forty minutes earlier** in a different session and a different
directory — and reported `Saved and verified`. Codex writes generated images to
`~/.codex/generated_images/<session>/` and then copies them out; when generation does not
produce a file, the model can "recover" by copying whatever else is sitting in that tree.

The report is not evidence. Hash the output against the others before showing it to anyone:

```bash
shasum -a 256 .impeccable/mocks/decision/*.png ~/.codex/generated_images/*/*.png | sort
```

A duplicate hash means that card did not generate. Delete the file and re-run — never present
it, and never let it reach the decision board, where it silently becomes a card the user might
lock. Cheap guard: generate into an empty directory and treat any pre-existing hash as a miss.

## Claims stay uninventable

Demonstration data is design material: author player names, ratings and report bodies at full
fidelity, and label them **synthetic on the image itself**. Commercial and factual claims are
not authorable — no prices, no real club crests or customer names, no benchmarks, no
"trusted by", no capability the product does not ship. Anything the composition wants but
cannot substantiate ships as a clearly marked placeholder on the owner's replacement list.

## The locked comp is a tracked artifact

`.gitignore` excludes `**/.impeccable/**` for impeccable's regenerable hook cache, with
negations that re-admit the decision comps and `DIRECTION.md`. The locked comp is what the
finish reviewer audits the build against, so it is committed; the spent hand is not.

Verify with `git check-ignore -v <path>` rather than assuming — a negation under an excluded
**directory** silently does nothing, which is why the exclusion is written against `/**`.
