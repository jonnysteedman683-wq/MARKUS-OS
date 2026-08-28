import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import tempfile
import shutil
from markus_db import PersistentCortexDB
from markus_context_pruner import MarkusContextPruner

def run_tests():
    # 1. DB Edge Cases
    temp_dir = Path(tempfile.mkdtemp())
    try:
        db = PersistentCortexDB(db_path=temp_dir / 'edge.db')
        
        # Compaction on empty DB
        c = db.compact_cortex()
        assert c['freed_bytes'] >= 0
        assert c['size_before'] >= 0
        assert c['size_after'] >= 0
        
        # None parameters
        assert db.prune_thoughts() == 0
        
        # max_entries = 0
        db.append_thought('e1', 'a', 'content 1')
        db.append_thought('e2', 'a', 'content 2')
        p = db.prune_thoughts(max_entries=0)
        assert p == 2
        assert db.get_cortex_stats()['total_thoughts'] == 0
        assert db.get_cortex_stats()['fts_indexed_count'] == 0
        
        # Special characters in content and registers
        db.set_register("weird'key\";--DROP", {"data": "it's cool & <xml>"})
        assert db.get_register("weird'key\";--DROP")["data"] == "it's cool & <xml>"
        db.append_thought("e3", "agent's", "content with ' quotes \" and symbols <>&")
        res = db.search_thoughts("quotes")
        assert len(res) == 1
        print("DB Edge Cases: PASSED")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    # 2. Context Pruner Edge cases
    pruner = MarkusContextPruner()
    
    # Empty inputs
    r1 = pruner.prune("", max_tokens=100)
    assert r1.retained_segments == 0 and r1.original_tokens == 0
    r2 = pruner.prune([], max_tokens=100)
    assert r2.retained_segments == 0

    # Zero token budget with invariant protection
    sample = ["Normal line", "PRIME-DIRECTIVE: protect me", "SyntaxError: bad"]
    r3 = pruner.prune(sample, max_tokens=0)
    assert "PRIME-DIRECTIVE" in r3.text
    assert "SyntaxError" in r3.text
    assert "Normal line" not in r3.text

    # Query with regex special chars
    r4 = pruner.prune(["hello [world] (test) +foo"], max_tokens=50, query="[world] +foo")
    assert r4.retained_segments == 1

    # Non-ASCII / Unicode
    unicode_sample = ["你好世界 Traceback: 发生错误", "обычный текст"]
    r5 = pruner.prune(unicode_sample, max_tokens=50)
    assert "Traceback" in r5.text

    print("Pruner Edge Cases: PASSED")

if __name__ == "__main__":
    run_tests()
