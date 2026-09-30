import os
import sys

if len(sys.argv) < 2:
    print("Error: No environment variable name provided to check.")
    sys.exit(1)

var_name = sys.argv[1]

if var_name not in os.environ or not os.environ[var_name].strip():
    print(f"Error: Environment variable '{var_name}' is not defined or is empty!")
    sys.exit(1)

print(f"Success: '{var_name}' is defined.")
sys.exit(0)
