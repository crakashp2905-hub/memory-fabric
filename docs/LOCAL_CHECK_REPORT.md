# Local test and capability report

`tools/local_check_report.py` combines a JUnit XML test run with the offline
baseline inventory. The JSON keeps passed, failed, and skipped test cases
separate from unavailable optional capabilities, records installed package
versions, and requires each unavailable capability to name its reason and the
acceptance arm it leaves untested.

Example:

```powershell
python -m pytest tests -q --junitxml=research/results/local-tests.xml
python tools/local_check_report.py --junit research/results/local-tests.xml --output research/results/local-check-report.json
```

The package/capability inventory is for the interpreter and host that produced
the report; it is not a cross-platform matrix claim.
