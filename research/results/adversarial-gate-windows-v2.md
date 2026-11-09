# Windows adversarial gate v2

Run on exact implementation commit `6b77d7d` with an explicit workspace-owned
temporary directory and loopback sockets permitted. All 21 adversarial families
passed without changing their tests or thresholds.

The sandboxed diagnostic run is intentionally not called a product failure:
it passed 19 families and the two HTTP families failed with Windows error 10013
because that sandbox denied loopback connections. The qualifying run used the
same code and tests outside that network restriction; it did not use external
network access.

Reproduce on Windows:

```powershell
python tools/adversarial_gate.py `
  --temp-dir .tmp-adversarial `
  --report adversarial-gate.json
```

Machine-readable result: [adversarial-gate-windows-v2.json](adversarial-gate-windows-v2.json).
