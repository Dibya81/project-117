# ADR 0002 - Remove ToolOrchestra from the working tree

- Status: accepted
- Date: 2026-09-09
- Phase: 0.5 (foundation hardening)
- Context: recorded during the Phase 0 audit, actioned in Phase 0.5.

## Context

The project began with five cloned repositories under `sih/`. The Phase 0 audit
inspected each one's implementation rather than its README, and ToolOrchestra
turned out not to be what its name suggests.

What it actually is:

- A **reinforcement-learning training harness** for NVIDIA's Orchestrator-8B
  model, plus the evaluation rigs (HLE, FRAMES, tau2-bench) used in the
  accompanying paper.
- Its runtime surface is `LLM_CALL.py`, whose helpers reach
  `https://prod.api.nvidia.com/llm/v1/azure/` and require `TAVILY_KEY`,
  `WANDB_API_KEY`, `OSS_KEY`, `CLIENT_ID`, `CLIENT_SECRET`.
- `training/` vendors verl (a distributed RL framework); `requirements.txt` is
  439 lines and assumes a multi-GPU training cluster.
- It writes a `keys/` directory with `os.chmod(..., 0o777)`.
- Disk cost in our tree: **97 MB**.

What it is **not**: a tool-routing library, an agent framework, or anything we
can import at runtime. There is no orchestration package to call - the routing
behaviour lives in *model weights*, not in reusable code.

## Decision

Remove `ToolOrchestra-main/` from the working tree. Keep the *idea* it
contributes, and nothing else.

The idea worth keeping is its tool-metadata schema. Phase 8 implements this in
our own registry, for our own tools:

```
tool metadata
  |- cost         (what this call costs us: tokens, seconds, money)
  |- latency      (expected wall-clock, so the planner can budget)
  |- capability   (what it can actually do)
  |- permissions  (who or what may invoke it)
  |- risk         (read-only? destructive? needs human approval?)
```

That schema is why the repo was cloned. It is five fields; it does not require
97 MB, an NVIDIA API key, or a GPU cluster.

## Consequences

- Nothing in `backend/` imports ToolOrchestra, so removal is not a code change.
  Verified by grep before deletion: zero references outside documentation.
- The RL training path (fine-tuning our own orchestrator model) is **not**
  closed off. If it is ever wanted, the upstream repository is public and the
  paper is cited below - re-clone it then, outside the product tree, on a
  machine with GPUs.
- Our orchestrator (Phase 6) is deterministic code plus a local reasoning
  model. It is not a trained routing model, and the audit report says so
  plainly rather than implying a borrowed capability we do not have.
- One less repository whose cloud API calls could be mistaken for part of the
  sovereign inference path.

## Execution

Deletion is not bundled into the Phase 0.5 patch, because a diff that removes
97 MB is unreviewable. Run the cleanup script deliberately:

```bash
./scripts/phase-0.5-cleanup.sh
```

If the tree is under version control, stage the removal explicitly
(`git rm -r --cached ToolOrchestra-main`) so history records the decision
alongside this document.

## References

- Paper: <https://arxiv.org/abs/2511.21689>
- Model: <https://huggingface.co/nvidia/Orchestrator-8B>
- Dataset: <https://huggingface.co/datasets/nvidia/ToolScale>
