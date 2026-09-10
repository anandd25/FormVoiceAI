import os
import sys
from dotenv import load_dotenv

load_dotenv()

REQUIRED_VARS = [
    "GROQ_API_KEY",
    "RIME_API_KEY",
]

missing = []
invalid = []

for name in REQUIRED_VARS:
    value = os.getenv(name)

    if not value:
        missing.append(name)
    elif value.startswith("your_") or value.startswith("<"):
        invalid.append(name)

if missing or invalid:
    print("❌ Secret preflight check FAILED")

    if missing:
        print("Missing variables:")
        for name in missing:
            print(f"  - {name}")

    if invalid:
        print("Placeholder values detected:")
        for name in invalid:
            print(f"  - {name}")

    print("\nCreate backend/.env with valid local credentials.")
    sys.exit(1)

print("✅ Secret preflight check PASSED")
print("Required API credentials are configured.")
print("Secrets are not displayed.")