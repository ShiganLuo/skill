---
name: developer-tool-documentation
description: "Audience-first writing for tool READMEs and developer docs."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [writing, documentation, readme, audience-first, developer-docs]
    category: productivity
---

# Developer Tool Documentation

Audience-first writing for READMEs, package docs, CLI help, and other documentation whose readers are people deciding whether to install and use a tool.

## When to Use This Skill

Use when the user asks to write or rewrite a README for a library, CLI, framework, or internal tool. Also use when a user describes existing docs as "too narrative", "too many principles", "feels like a personal blog", "another person wouldn't understand", or "AI-flavored" — these are usually structural critiques, not just prose ones.

Do not use for blog posts, essays, personal portfolios, academic papers, or design documents whose audience is the author themselves.

## The Core Rule

**The reader is a potential user with a problem. They want to know (1) can this solve my problem and (2) how do I call it. Everything else is noise.**

Before drafting, ask: *who reads this and what decision are they about to make?*

| Reader moment | They want to see |
| --- | --- |
| Landing on the README | "This is what it is, does it solve my problem, can I install it now" |
| Looking for a command | The exact CLI invocation with a working example |
| Stuck mid-run | A flag reference or troubleshooting table |
| Evaluating alternatives | Side-by-side comparison with the obvious alternatives |

Anything that does not advance one of those moments does not belong in the opening sections.

## When to Load This Skill

Load when the user asks to:
- write or rewrite a README for a project, library, CLI, or internal tool
- review a README that "doesn't feel right" or "reads weird"
- structure documentation that the user describes as "too narrative", "has too many principles", "feels like a personal blog", or "another person wouldn't understand why I built it"

Do not load for blog posts, essays, personal portfolios, academic papers, or design documents whose audience is the author themselves.

## Structural Template (the "解决什么问题" pattern)

The opening section of a tool README should answer three questions in this order:

1. **What does this tool do?** One sentence. No backstory.
2. **What problems does it solve for me?** Bulleted pain → solution pairs, each ending with a concrete CLI/API snippet.
3. **How do I start?** A single `pip install` / `brew install` / `clone && run` command.

Everything else (architecture, philosophy, design principles, comparison to competitors, roadmap) belongs in later sections that interested readers can scroll to. The reader who bounces in the first 30 lines never reaches them, and that is the right outcome — they were not the audience.

## Section-by-Section Guidance

### Opening (first 30-50 lines)

- Lead with the **problem this solves**, not the tool's existence.
- Use a "Pain → Solution → Command" triplet for each major capability.
- Include 2-3 working code blocks, not pseudocode.
- Do not start with "Welcome to X" / "X is a powerful tool for..." / "In today's rapidly evolving...". These signal that the doc is about the tool, not the reader.

### "Why I built this" / Origin Story

**Do not include this section.** The reader does not care about your history, your failed projects, your epiphany at 3am, or your comparison shopping among tools. If you want to write that, put it in a blog post or `docs/PROLOGUE.md` and link to it from the bottom of the README.

If a stakeholder insists, the right place is a `## Motivation` section *after* the install/quickstart, and it should be 10 lines, not 30.

### "Design Principles" / Architecture Philosophy

**Do not include this in a tool README.** Principles belong in:
- Internal design docs (audience: contributors)
- ADRs (audience: future maintainers)
- Conference talks (audience: peers)
- Blog posts (audience: people interested in your thinking)

A README reader scanning for "will this solve my problem" will skip this section, and a reader who already trusts you does not need it.

If the principles are load-bearing for understanding the tool (e.g. "this is a streaming library, everything is lazy"), encode them in the API name, the CLI help text, and the error messages. Do not document them in a separate section.

### "Pipeline / Stack Selection" / "Why X not Y"

**Do not include this in a tool README.** The reader already chose your tool — they are reading your README, not your competitor's. Selection rationale is interesting to you, not to them.

If you must acknowledge alternatives, one sentence: "If you need [competing feature], look at [competitor]." Move on.

### Comparison Tables (rows = principles, columns = tools)

Almost always wrong. They tell the author "I considered all the options" but the reader sees an unreadable grid that does not answer any concrete question. Replace with 2-3 lines of prose stating when this tool is the right choice and when it is not.

### The One Acceptable Exception

If your tool's *entire value proposition* is "I made the boring choice so you don't have to", then a brief "why I picked Snakemake over Nextflow" can land. But it goes at the bottom, is 5-10 lines, and acknowledges that the alternatives are also valid choices.

## Writing Mechanics (post-structure)

Once the structure is right, apply these mechanical rules:

1. **First 100 words must earn the reader's next 60 seconds.** No throat-clearing.
2. **One sentence per paragraph in opening sections.** Long paragraphs signal "essay" to the reader's scanner.
3. **Code blocks before prose explanations.** Show, then explain. Not the other way around.
4. **Cut every "I" that is not about a decision the reader needs to know.** "I built this in 2023 because..." → delete. "I recommend X over Y for Z reason" → keep.
5. **No boldface emphasis in opening sections.** Bold runs signal "presentation", which signals "this is not a working tool, this is a pitch".
6. **No closing paragraph that summarizes what you just said.** The reader who read it does not need it; the reader who skipped will not read it.

## The Reader-First Self-Test

Before claiming the doc is done, run this test aloud:

> "I am a graduate student with a WGS dataset. I have never heard of this tool. I just clicked the link. Why should I install it, and what command do I run first?"

If the answer is buried in a personal story, a principle list, or a competitor comparison, the opening needs work. The opening is what converts strangers; everything else converts the already-interested.

## Anti-Patterns Specific to This Class

Beyond the general "AI flavor" tells (covered by the `humanizer` skill), tool README writing has its own failure modes:

| Anti-pattern | Symptom | Fix |
| --- | --- | --- |
| The origin story | "In 2023, I started this project because..." | Delete the section. |
| The principles sermon | "We believe in [philosophy]. We believe in [philosophy]..." | Encode the principle in the API, not the doc. |
| The competitor comparison | "Unlike Tool X which does Y, we do Z" | One sentence acknowledging the alternative; no comparison table. |
| The "what's coming" roadmap | Long bulleted TODO list in the opening | Move to a separate ROADMAP.md, link from bottom. |
| The triple-threat opener | "Fast, simple, and powerful." | Pick one claim, back it with a number or example. |
| The screenshot hero | One big screenshot of the dashboard | Replace with one copy-pasteable command and its output. |

## When the User Pushes Back

Common feedback patterns and what they actually mean:

| User says | What they mean | Fix |
| --- | --- | --- |
| "不是很吸引人" | The opening does not hook them as a reader | Lead with a concrete problem they have, not a tool description |
| "AI味道太浓了" | Sentences are too symmetrical, too quotable, too "essay-like" | See `humanizer` skill for prose-level cleanup |
| "另个人只想知道能否解决问题" | The audience is not the author | Cut personal stories, principles, design rationale; show pain → solution → command |
| "太啰嗦了" | Reader cannot scan to the actionable content | First sentence of every section must be the takeaway |
| "我自己写的更自然" | The doc sounds too polished, too generic | Use the user's actual voice; cut the AI-style parallelism |

When the user gives the first three, assume they mean the **structural** critique (audience is wrong), not just prose cleanup. Prose polish will not fix a structurally wrong doc.

## Iteration Pattern

When rewriting tool docs in a session, expect 2-4 rounds:

1. **Round 1**: First cut at the audience-first structure.
2. **Round 2**: User pushes back on tone, AI flavor, or missing concrete commands.
3. **Round 3**: User asks to remove personal stories / principles / philosophy.
4. **Round 4** (optional): Prose-level cleanup.

Do not skip rounds. Each round is the user narrowing in on what they actually want. Resist the temptation to write the "final" version on round 1 — you will get it wrong, and the user will not trust the rewrite.

## Related Skills

- `humanizer` — for prose-level cleanup of AI tells once structure is right
- `requesting-code-review` — for getting technical accuracy feedback on doc examples
- `scientific-report-ppt` — for slide-deck format (not README), but shares the "audience first" principle

## Reference Files

- `references/omics-readme-session.md` — worked example from a 4-round README rewrite; shows the user's progressive feedback pattern (prose critique → structural critique → final solution).