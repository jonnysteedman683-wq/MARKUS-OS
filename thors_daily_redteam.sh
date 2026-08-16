#!/bin/bash
# Daily Thors Red Team validation — runs the attack simulator
cd /c/Users/jonny/OneDrive/Desktop/New\ folder
python markus_attack_simulator.py 2>&1 | grep -E "SIMULATION|Success|Detected|Total|Exit|Profile"
echo "---"
# Check if detection rate is 100%
if python markus_attack_simulator.py 2>&1 | grep -q "Success rate:    100.0%"; then
    echo "SECURITY STATUS: GREEN - 17/17 attacks detected"
else
    echo "SECURITY STATUS: AMBER - detection rate below 100%"
fi
