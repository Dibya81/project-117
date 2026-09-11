"""Model providers — the gateway's pluggable backends.

Phase 2 ships one provider: OpenAI-compatible (serves Ollama's /v1 and vLLM).
More providers (native Ollama, llama.cpp, …) can be added without touching
callers — everything above this layer talks to ``ModelProvider``.
"""