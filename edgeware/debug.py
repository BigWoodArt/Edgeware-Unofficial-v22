import subprocess
import sys
from pathlib import Path

from src.paths import Process

HERE = Path(__file__).resolve().parent

# TODO: Running individual features
print("""Which feature would you like to run?
0. Quit
1. Edgeware (start.py)
2. Config (config.pyw)""")

processes = [
    [Process.MAIN],
    [str(HERE / "config.pyw")],  # Process.CONFIG points at the old, superseded main_config.py - config.pyw is the real, current one
]  # fmt: off

while True:
    num = input("Select number: ")
    try:
        num = int(num)
    except Exception:
        print("Input must be an integer")
        continue

    if num == 0:
        break
    elif num > 0 and num <= len(processes):
        subprocess.run([sys.executable] + processes[num - 1])
        print("Done")
    else:
        print("Input must be between 0 and 2")

print("Goodbye!")
