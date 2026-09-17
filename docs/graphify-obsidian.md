# Graphify → Obsidian

Project 117's source tree is mirrored into a local Obsidian vault as a
queryable knowledge graph, built entirely on this machine.

**Vault:** `/Users/dibyabhusal/Desktop/projects/memory`
**Graph:** `Project117/` (4385 notes + `graph.canvas` + `_GRAPHIFY_REPORT.md`)

Open Obsidian, pick that vault, and use **Graph view** — or open
`Project117/graph.canvas` for the community-grouped layout.

## What is in there

| | |
| --- | --- |
| Nodes | 4159 (functions, classes, files, modules) |
| Edges | 9114 |
| Notes | 4385 |
| Wikilinks | 24162 — **100% resolved, 0 broken** |
| Communities | 226, named by a local Ollama model |

Every note carries frontmatter (`source_file`, `type`, `community`,
`location`, tags) and a `## Connections` section of typed wikilinks
(`calls`, `imports`, `uses`, `method`, …) tagged `EXTRACTED` (parsed from the
AST) or `INFERRED` (semantic). Community overview notes are prefixed
`_COMMUNITY_` so they sort to the top of the folder.

## Why the labels are trustworthy

Community naming ran against the **local Ollama** server
(`llama3:latest` on `127.0.0.1:11434`), matching Project 117's sovereign,
on-prem posture. No source code, path or symbol name left the machine. Names
came out grounded in the codebase — `JobService`, `MemoryRetriever`,
`create_app`, `WorkflowRunState`, `AnimatedTopDock.tsx` — not generic filler.

## Rebuild

```bash
./scripts/graphify-obsidian.sh                 # full rebuild + publish
./scripts/graphify-obsidian.sh --no-label      # skip LLM community naming
OBSIDIAN_VAULT=~/some/vault ./scripts/graphify-obsidian.sh
OLLAMA_MODEL=qwen2.5:14b-instruct-q4_K_M ./scripts/graphify-obsidian.sh
```

Extraction is `--code-only`: a local tree-sitter AST pass, deterministic and
offline. Only community naming touches a model, and only the local one.

## Query it

```bash
.graphify-venv/bin/graphify query "how does approval flow to execution?"
.graphify-venv/bin/graphify path "create_app" "JobService"
.graphify-venv/bin/graphify explain "JobService"
.graphify-venv/bin/graphify god-nodes --top 15
.graphify-venv/bin/graphify affected "SimulationStore" --depth 2
```

## Safety

The install is **additive**. It writes only into `Project117/`, a new
subfolder. Your existing 1507 notes in `Documents/`, `Jarvis/`, `Others/` are
untouched, and `.obsidian/` config was not modified. Re-runs overwrite only
notes graphify owns; a file it did not generate is never replaced.

## Notes

- The secret scanner flagged `src/styles/tokens.css` as potentially sensitive
  (a false positive on the filename), so graphify skipped it. It is absent
  from the graph.
- `--code-only` means 52 docs and 241 images were not ingested. Run
  `graphify extract .` without the flag (needs a model backend) to include
  prose and diagrams.
