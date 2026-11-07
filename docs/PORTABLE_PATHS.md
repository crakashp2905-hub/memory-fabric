# Portable paths and text files

Persisted text uses explicit UTF-8. Freshness lease snapshots write LF line
endings, while JSONL imports accept LF, CRLF and CR input. Path fixtures use
`pathlib` components and include spaces and non-ASCII names/content; no test
assumes the host separator or locale encoding.

The test suite also checks every Git-tracked path after Unicode case folding.
That catches names that can coexist on a case-sensitive checkout but collide
on common Windows and macOS filesystems.

Run:

```bash
python -m unittest tests.test_portable_paths tests.test_freshness tests.test_eventlog
```

CI runs the full suite on Ubuntu, Windows and macOS with Python 3.11, 3.12 and
3.13.
