# Minority source and majority-copy benchmark v1

Three fixed seeds (901, 907, 911) each produce one held-out scenario with 50 agents: one rare source states the verified true value, one majority source states the false value, and 48 agents repeat that majority source. The majority copies share one provenance root; the minority observation is an independent root.

Arms: majority vote, minority-source policy, Memory Fabric action authorization over the contested evidence, and oracle. The truth label is `allow`; all arms receive the same scenario identity and the report separates the rare minority agent from the 49-agent majority mean and the population mean.

Report task success, false refusal, unsafe action, source-root counts, independent support roots, contested state, and blocking reason. Any confidence derived from the majority's copies must not count them as 49 independent sources. This is a local scripted experiment, not a real-agent consensus study.
