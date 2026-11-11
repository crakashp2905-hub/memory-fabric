# UTCP manual policy checks

The supported UTCP subset is parsed by `discover_utcp` in `memory_fabric.tool_protocol`. It validates the pinned protocol/manual versions, tool names, schema subset, transport type, URL shape, HTTP method, duplicate names and unknown security fields. Discovery is pure over an already parsed mapping; it does not fetch URLs, resolve DNS, open files, or create sockets.

The N6-06 fixture loads the frozen corpus first, then arms guards for `socket.socket`, `Path.open`, `builtins.open` and `urllib.request.urlopen`. All 24 malicious and unsupported-version manuals must raise `ToolProtocolError` while the guards remain inactive; a control manual with a public HTTPS endpoint must still parse. This establishes parser behavior, not endpoint trust or DNS/TLS behavior.
