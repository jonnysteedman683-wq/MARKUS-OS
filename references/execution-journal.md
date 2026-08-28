The MARKUS execution journal module provides append-only lifecycle tracking for task side effects.

Key features:
- ExecutionJournal: replayable journal with deterministic completion detection
- ManualRecoveryRequired: explicit gate for uncertain side effects
- Secret redaction in JSON output

Typical usage:
    journal = ExecutionJournal("/path/to/journal.jsonl")
    result = journal.run("run-42:fetch", recovery="idempotent", action=fetch_data)

Recovery policies:
- idempotent: May re-execute on resume without user intervention
- reconcile: Same as idempotent (pending implementation)
- manual: Halts and requires human authorization on incomplete steps

Journal format:
{"execution_id":"run-42:fetch","state":"started|completed|failed|manual_required","recovery":"idempotent|manual","attempt":1,"result":...,"timestamp":"..."}