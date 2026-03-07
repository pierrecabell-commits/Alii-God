#!/usr/bin/env python3
"""
PR Agent / Pre-commit Hook — blocks sensitive data from commits.
Install: cp agents/pr_agent.py .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
"""
import re, subprocess, sys
from pathlib import Path

BLOCKED_PATTERNS = [
    # Private IPs
    (r"192\.168\.\d+\.\d+",           "Private LAN IP"),
    (r"\b10\.\d+\.\d+\.\d+\b",        "Private IP (10.x)"),
    (r"172\.(1[6-9]|2\d|3[01])\.\d+\.\d+", "Private IP (172.x)"),
    # Tailscale IPs
    (r"100\.\d+\.\d+\.\d+",           "Tailscale IP"),
    # Internal hostnames
    (r"\baliirecision\b",              "Internal hostname: aliirecision"),
    (r"\baliiaiserv\w+",               "Internal hostname: aliiaiserver"),
    (r"\bxpsavalii\w+",                "Internal hostname: xpsavaliiserver"),
    # Phone numbers
    (r"\+?1?\s*\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}", "Phone number"),
    # Sensitive file references (for public repo)
    (r"accounts_registry\.json",       "Private: accounts_registry.json"),
    (r"saas\.db",                      "Private: saas.db"),
    (r"\.alii_vault",                  "Private: vault directory"),
    # API key patterns
    (r"sk-[a-zA-Z0-9]{20,}",          "API key (sk-)"),
    (r"ghp_[a-zA-Z0-9]{36}",          "GitHub token"),
    (r"pplx-[a-zA-Z0-9]{40,}",        "Perplexity API key"),
]

# These files are always skipped (they're expected to contain patterns)
SKIP_FILES = {".env.example", "pr_agent.py", ".gitignore"}

def get_staged_files() -> list[str]:
    r = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
                       capture_output=True, text=True)
    return [f for f in r.stdout.strip().splitlines() if f]

def check_file(filepath: str) -> list[tuple[int, str, str]]:
    if Path(filepath).name in SKIP_FILES:
        return []
    try:
        content = Path(filepath).read_text(errors="replace")
    except (FileNotFoundError, IsADirectoryError):
        return []

    violations = []
    for lineno, line in enumerate(content.splitlines(), 1):
        for pattern, description in BLOCKED_PATTERNS:
            if re.search(pattern, line, re.I):
                violations.append((lineno, description, line.strip()[:80]))
    return violations

def main():
    staged = get_staged_files()
    if not staged:
        sys.exit(0)

    all_violations = {}
    for filepath in staged:
        violations = check_file(filepath)
        if violations:
            all_violations[filepath] = violations

    if not all_violations:
        print("Pre-commit: No sensitive data detected")
        sys.exit(0)

    print("\nCOMMIT BLOCKED -- Sensitive data detected:\n")
    for filepath, violations in all_violations.items():
        print(f"  {filepath}:")
        for lineno, desc, line in violations[:5]:
            print(f"    Line {lineno}: [{desc}] {line}")

    print("\nFix these issues before committing.")
    print("To skip (DANGEROUS): git commit --no-verify")
    sys.exit(1)

if __name__ == "__main__":
    main()
