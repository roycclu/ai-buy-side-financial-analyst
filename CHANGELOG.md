# Changelog

All notable project updates are logged here. Each entry is timestamped and kept under 300 characters.

---

## Updates

| Timestamp | Change |
|---|---|
| 2026-02-22 | Initial git repository setup. Added .gitignore (excludes .env, __pycache__, outputs, Financial Files). Project baseline committed with agents, tools, utils, orchestration, config, and observability modules. |
| 2026-02-22 | Added local LLM support via Ollama. New llm/ adapter module (base, anthropic, ollama, factory). All 4 agents refactored to provider-agnostic adapter pattern. Set LLM_PROVIDER=ollama + LOCAL_MODEL in .env to use local models. |
