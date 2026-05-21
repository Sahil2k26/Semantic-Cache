"""Read test output and write to UTF-8 file."""
import subprocess, sys

result = subprocess.run(
    [sys.executable, "-m", "pytest", 
     "tests/unit/test_phase1_1_foundation.py", 
     "tests/test_multi_intent.py",
     "-v", "--tb=short", "--no-header"],
    capture_output=True, text=True, cwd="."
)

with open("_test_results_readable.txt", "w", encoding="utf-8") as f:
    f.write("STDOUT:\n")
    f.write(result.stdout)
    f.write("\nSTDERR:\n")
    f.write(result.stderr)
    f.write(f"\nRETURN CODE: {result.returncode}\n")

print(f"Done. Return code: {result.returncode}")
