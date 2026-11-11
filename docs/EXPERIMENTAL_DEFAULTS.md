# Experimental features and default behavior

Module stability tiers are generated in `STABILITY.md`. The standard entry
points (package import, `MemoryFabric`, SDK, service, agent HTTP, presets, CLI,
and MCP) are statically checked not to import experimental modules at module
scope. Experimental features must be invoked through an explicit opt-in path.

Preset store settings, protected-tool defaults, and MCP flags are frozen in
`tests/data/default_features.json`. A reviewed default change must update that
snapshot in the same change and explain its migration or safety impact. MCP's
extended tools and `trusted_local` behavior remain off by default; the personal
preset is an explicit selection and is recorded at store initialization.

Run `python -m pytest tests/test_stability.py tests/test_presets.py
tests/test_mcp_extended.py` to verify import boundaries, the preset snapshot,
and explicit opt-in behavior.
