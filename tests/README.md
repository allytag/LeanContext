# Test Layout

- `tests/` = shared repo tests, shared fixtures, and standalone root hook tests
- `tests/shared/leancontext-compress/` = shared compression benchmark fixtures
- `codex/tests/` = Codex export/package verification
- `claude/tests/` = Claude export/package verification + Claude-export fixture copies

Current files:

- `tests/test_installers.py` checks root `install.py` / `uninstall.py` flows in temp homes only
- `tests/test_hooks.py` checks standalone root `hooks/` install/uninstall flow
- `tests/shared/leancontext-compress/` holds shared fixture pairs for benchmark scripts
- `codex/tests/verify_repo.py` checks Codex export parity and gate
- `claude/tests/verify_repo.py` checks Claude export parity and gate
