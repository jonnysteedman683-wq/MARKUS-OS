#!/usr/bin/env python3
"""Commit script for MARKUS TCP mesh reliability enhancements"""
import subprocess
import os

working_dir = r"C:\Users\jonny\OneDrive\Desktop\New folder"

# Initialize git repo if needed
if not os.path.exists(os.path.join(working_dir, '.git')):
    subprocess.run(['git', 'init'], cwd=working_dir, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'phoenix@phenome.local'], cwd=working_dir, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'PHOENIX'], cwd=working_dir, capture_output=True)
    
    # Create .gitignore
    gitignore = """# Python
__pycache__/
*.pyc
*.pyo
*.egg-info/
.venv/
venv/
.env

# SQLite
*.db
"""
    with open(os.path.join(working_dir, '.gitignore'), 'w') as f:
        f.write(gitignore)
    
    print("Git repo initialized")
else:
    print("Git repo already exists")

# Add all files
result = subprocess.run(['git', 'add', '.'], cwd=working_dir, capture_output=True, text=True)
print("Add output:", result.stdout, result.stderr)

# Commit
commit_msg = """feat: MARKUS OS TCP mesh reliability enhancements

- UDP gossip: Windows loopback fix for 255.255.255.255 broadcast
- TCP reliability mode with Lamport clock anti-entropy sync
- TCP connection pooling with LRU eviction and health checks
- Adaptive UDP->TCP fallback detector (10% loss threshold)
- Comprehensive integration test suite

All 35/35 battle tests verified and passing."""

result = subprocess.run(['git', 'commit', '-m', commit_msg], cwd=working_dir, capture_output=True, text=True)
print("Commit result:")
print(result.stdout)
if result.stderr:
    print(result.stderr)

print("Exit code:", result.returncode)