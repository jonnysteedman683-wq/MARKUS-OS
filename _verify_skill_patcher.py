"""End-to-end verification that CortexSkillPatcher now resolves and patches skills."""
import sys, os, tempfile, shutil
sys.path.insert(0, r"C:/Users/jonny/OneDrive/Desktop/MARKUS-OS")

from markus_cortex_skill_patcher import CortexSkillPatcher
from pathlib import Path

ok = True
patcher = CortexSkillPatcher()  # uses fixed HERMES_SKILLS_ROOT

# 1) Every pattern-target skill must now resolve to a LIVE (non-archive) SKILL.md
targets = ["self-evolution-and-code-optimization",
           "markus-os-development"]
print("=== 1. Skill file resolution (real root, live only) ===")
for name in targets:
    f = patcher._find_skill_file(name)
    found = f is not None and f.exists() and ".archive" not in f.parts
    ok &= found
    print(f"  {'[FOUND]' if found else '[MISSING]'} {name} -> {f}")

# frontend-backend-telemetry-and-cleanup must now be SKIPPED (archived) — confirm no live match
archived = patcher._find_skill_file("frontend-backend-telemetry-and-cleanup")
archive_ok = archived is None
ok &= archive_ok
print(f"  [SKIPPED-ARCHIVED] frontend-backend-telemetry-and-cleanup -> live match: {archive_ok}")

# 2) analyze_thought must generate patches (no 'not found' path)
print("\n=== 2. analyze_thought generates patches ===")
thought = "Debate verdict confidence=0.9 consensus=REACH on the backend refactor; also caught ImportError in markus_router"
patches = patcher.analyze_thought("test_001", "AURORAL", thought, {})
print(f"  generated {len(patches)} patch(es)")
for p in patches:
    print(f"    -> {p.skill_name} [{p.action}]")
ok &= len(patches) >= 1

# 3) auto_patch_skill write path (isolated temp root, real skill name)
print("\n=== 3. auto_patch_skill actually writes (temp root) ===")
tmp = tempfile.mkdtemp(prefix="skillpatch_")
try:
    skill_dir = os.path.join(tmp, "markus-os-development")
    os.makedirs(skill_dir)
    skill_md = os.path.join(skill_dir, "SKILL.md")
    with open(skill_md, "w", encoding="utf-8") as fh:
        fh.write("---\nname: markus-os-development\n---\n\n# Body\n")
    tmp_patcher = CortexSkillPatcher(skills_root=Path(tmp))
    p2 = tmp_patcher.analyze_thought("test_002", "AURORAL",
                                     "ImportError in handler alias mapping", {})
    wrote = False
    for p in p2:
        if p.skill_name == "markus-os-development":
            wrote = tmp_patcher.auto_patch_skill(p)
    content = open(skill_md, encoding="utf-8").read() if wrote else ""
    anchor_ok = wrote and "# === Auto-Patch Section ===" in content
    ok &= anchor_ok
    print(f"  patch applied: {wrote}, anchor present: {anchor_ok}")
    if anchor_ok:
        print(f"  appended line: {[l for l in content.splitlines() if 'Backend fix pattern' in l][:1]}")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\n=== RESULT:", "ALL GREEN" if ok else "FAILURES PRESENT", "===")
sys.exit(0 if ok else 1)
