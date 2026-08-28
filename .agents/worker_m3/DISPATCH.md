## 2026-08-27T02:27:49Z
Milestone M3: Local Memory & Context Compaction Engine (`markus_db.py`, `markus_context_pruner.py`).
Working directory: C:\Users\jonny\OneDrive\Desktop\MARKUS-OS\.agents\worker_m3
Authoritative request: C:\Users\jonny\OneDrive\Desktop\MARKUS-OS\.agents\ORIGINAL_REQUEST.md
Master project blueprint: C:\Users\jonny\OneDrive\Desktop\MARKUS-OS\PROJECT.md
Survey inputs: C:\Users\jonny\OneDrive\Desktop\MARKUS-OS\.agents\explorer_survey_3\survey_r3.md and handoff.md

Exclusive write ownership:
- `markus_db.py`
- `markus_context_pruner.py`
Do NOT modify any other files.

Detailed Tasks:
1. Read ORIGINAL_REQUEST.md, PROJECT.md, and survey_r3.md before making changes.
2. Enhance `markus_db.py`:
   - Implement `prune_thoughts(max_age_seconds: Optional[int] = None, max_entries: Optional[int] = None) -> int`:
     Prunes older or excess thought records from the `thoughts` table while keeping the most recent entries within `max_entries` or younger than `max_age_seconds`. Crucially, synchronously delete matching rows from `thoughts_fts` table. Returns count of pruned thought rows.
   - Implement `compact_cortex() -> Dict[str, Any]`:
     Executes SQLite `VACUUM` and `ANALYZE`, measures DB file size before and after, returns compaction metrics (`freed_bytes`, `size_before`, `size_after`, `timestamp`).
   - Implement `get_cortex_stats() -> Dict[str, Any]`:
     Returns summary dictionary containing register count, total thoughts count, FTS indexed count, DB path, and file size in bytes.
   - Ensure thread-safe connection handling and transaction integrity.
   - Add / expand internal self-test `_test_db()` verifying registers, thoughts, FTS search, pruning, compaction, and stats.
3. Enhance `markus_context_pruner.py`:
   - Ensure robust AST/salience token importance scoring, structural invariant protection (`Traceback`, `SyntaxError`, `AssertionError`, `PRIME-DIRECTIVE`), and greedy token packing within target budget.
   - Verify that `_test_context_pruner()` passes cleanly.
4. Verification:
   - Run `python -m py_compile markus_db.py markus_context_pruner.py`
   - Run `python markus_db.py`
   - Run `python markus_context_pruner.py`
   - Run `python hermes_verify_evolution_loops.py`
5. Documentation:
   - Write your complete handoff report to `C:\Users\jonny\OneDrive\Desktop\MARKUS-OS\.agents\worker_m3\handoff.md` with: 1. Observation, 2. Logic Chain, 3. Caveats, 4. Conclusion, 5. Verification Method.
   - Use send_message to report back to your parent orchestrator with a summary of changes and verification results.
