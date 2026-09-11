#!/usr/bin/env bash
# Build the Project 117 knowledge graph with graphify and publish it into the
# local Obsidian vault.
#
#   ./scripts/graphify-obsidian.sh                 # full rebuild + publish
#   ./scripts/graphify-obsidian.sh --no-label      # skip LLM community naming
#   OBSIDIAN_VAULT=/path/to/vault ./scripts/graphify-obsidian.sh
#
# Everything runs on this machine. Community naming uses the local Ollama
# server, so no source code, path or symbol name ever leaves the box.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GRAPHIFY_VENV="${GRAPHIFY_VENV:-$REPO/.graphify-venv}"
GRAPHIFY="$GRAPHIFY_VENV/bin/graphify"
STAGING="$REPO/graphify-out/obsidian"

# The vault Obsidian currently has open. Override with OBSIDIAN_VAULT.
OBSIDIAN_VAULT="${OBSIDIAN_VAULT:-$HOME/Desktop/projects/memory}"
TARGET="$OBSIDIAN_VAULT/Project117"

# Local model used to name communities. Any model `ollama list` shows will do.
OLLAMA_MODEL="${OLLAMA_MODEL:-llama3:latest}"
LABEL=1
[[ "${1:-}" == "--no-label" ]] && LABEL=0

if [[ ! -x "$GRAPHIFY" ]]; then
  echo "graphify is not installed at $GRAPHIFY" >&2
  echo "  python3 -m venv .graphify-venv" >&2
  echo "  .graphify-venv/bin/pip install graphifyy openai" >&2
  exit 1
fi

cd "$REPO"

echo "==> extracting code graph (local AST, no network)"
"$GRAPHIFY" extract . --code-only

echo "==> clustering"
"$GRAPHIFY" cluster-only . --no-viz --no-label

if [[ "$LABEL" == "1" ]]; then
  if curl -sf -m 5 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    echo "==> naming communities with local Ollama model: $OLLAMA_MODEL"
    "$GRAPHIFY" label . --backend=ollama --model="$OLLAMA_MODEL" \
      --max-concurrency=1 --batch-size=40 --missing-only || \
      echo "    (labeling failed - keeping numeric community names)"
  else
    echo "==> Ollama not reachable on :11434 - skipping community naming"
  fi
fi

echo "==> exporting Obsidian vault"
"$GRAPHIFY" export obsidian

echo "==> publishing to $TARGET"
mkdir -p "$TARGET"
# Copy over the top. graphify only ever writes its own generated notes, and a
# pre-existing file it does not own is left alone, so a hand-written note in
# this folder is never clobbered.
cp -R "$STAGING/." "$TARGET/"
cp "$REPO/graphify-out/GRAPH_REPORT.md" "$TARGET/_GRAPHIFY_REPORT.md"

NOTES=$(find "$TARGET" -name '*.md' | wc -l | tr -d ' ')
echo
echo "Done. $NOTES notes in $TARGET"
echo "Open Obsidian -> that vault -> Project117/. The folder is part of the"
echo "vault, so it is already indexed; use Graph view or open graph.canvas."
