"""Shared cross-host installer tests for root install/uninstall entrypoints."""

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


class InstallerTests(unittest.TestCase):
    def run_cmd(self, cmd, home, extra_env=None):
        env = os.environ.copy()
        env["HOME"] = str(home)
        env["USERPROFILE"] = str(home)
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )

    def test_codex_install_and_uninstall_use_local_copy(self):
        with tempfile.TemporaryDirectory(prefix="leancontext-codex-install-") as tmp:
            home = Path(tmp)
            codex_dir = home / ".codex"
            codex_dir.mkdir(parents=True)
            (codex_dir / "config.toml").write_text('model = "gpt-5.4"\n')

            self.run_cmd([sys.executable, "install.py", "--codex"], home)

            plugin_root = home / "plugins" / "leancontext"
            self.assertTrue(plugin_root.exists())
            self.assertFalse(plugin_root.is_symlink())
            manifest = json.loads((plugin_root / ".codex-plugin" / "plugin.json").read_text())
            self.assertEqual(manifest["name"], "leancontext")

            marketplace = json.loads((home / ".agents" / "plugins" / "marketplace.json").read_text())
            names = [plugin["name"] for plugin in marketplace["plugins"]]
            self.assertIn("leancontext", names)

            config_text = (codex_dir / "config.toml").read_text()
            self.assertIn('[plugins."leancontext@local"]', config_text)
            self.assertIn("enabled = true", config_text)

            self.run_cmd([sys.executable, "uninstall.py", "--codex"], home)

            self.assertFalse(plugin_root.exists())
            self.assertFalse((home / ".codex" / "plugins" / "cache" / "local" / "leancontext").exists())
            config_text = (codex_dir / "config.toml").read_text()
            self.assertIn('[plugins."leancontext@local"]', config_text)
            self.assertIn("enabled = false", config_text)

    def test_claude_install_and_uninstall_shell_out_via_cli(self):
        with tempfile.TemporaryDirectory(prefix="leancontext-claude-install-") as tmp:
            home = Path(tmp)
            bin_dir = home / "bin"
            bin_dir.mkdir()
            log_path = home / "claude.log"
            claude_path = bin_dir / "claude"
            claude_path.write_text(
                "#!/bin/sh\n"
                "printf '%s\\n' \"$@\" >> \"$LEANCONTEXT_CLAUDE_LOG\"\n"
                "exit 0\n"
            )
            claude_path.chmod(claude_path.stat().st_mode | stat.S_IEXEC)

            env = {
                "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
                "LEANCONTEXT_CLAUDE_LOG": str(log_path),
            }

            self.run_cmd([sys.executable, "install.py", "--claude"], home, env)
            self.run_cmd([sys.executable, "uninstall.py", "--claude"], home, env)

            log_lines = log_path.read_text().splitlines()
            joined = "\n".join(log_lines)
            self.assertIn("plugin", joined)
            self.assertIn("marketplace", joined)
            self.assertIn("install", joined)
            self.assertIn("enable", joined)
            self.assertIn("disable", joined)
            self.assertIn("uninstall", joined)

    def test_install_dry_run_auto_detects_targets(self):
        with tempfile.TemporaryDirectory(prefix="leancontext-install-dry-run-") as tmp:
            home = Path(tmp)
            (home / ".codex").mkdir(parents=True)
            (home / ".codex" / "config.toml").write_text('model = "gpt-5.4"\n')

            bin_dir = home / "bin"
            bin_dir.mkdir()
            claude_path = bin_dir / "claude"
            claude_path.write_text("#!/bin/sh\nexit 0\n")
            claude_path.chmod(claude_path.stat().st_mode | stat.S_IEXEC)

            result = self.run_cmd(
                [sys.executable, "install.py", "--dry-run"],
                home,
                {"PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"},
            )

            self.assertIn("Codex install source", result.stdout)
            self.assertIn("Claude install source", result.stdout)
            self.assertIn("[DONE] dry-run finished", result.stdout)

    def test_remote_stdin_installer_stages_repo_when_not_in_checkout(self):
        with tempfile.TemporaryDirectory(prefix="leancontext-stdin-install-") as tmp:
            home = Path(tmp) / "home"
            cwd = Path(tmp) / "cwd"
            home.mkdir()
            cwd.mkdir()
            (home / ".codex").mkdir(parents=True)
            (home / ".codex" / "config.toml").write_text('model = "gpt-5.4"\n')

            script = (REPO_ROOT / "install.py").read_text()
            env = os.environ.copy()
            env["HOME"] = str(home)
            env["USERPROFILE"] = str(home)

            result = subprocess.run(
                [sys.executable, "-", "--codex", "--dry-run"],
                cwd=cwd,
                env=env,
                input=script,
                text=True,
                capture_output=True,
                check=True,
            )

            self.assertIn("local repo not found. staging", result.stdout)
            self.assertIn("download:", result.stdout)

    def test_codex_install_refuses_unmanaged_symlink(self):
        with tempfile.TemporaryDirectory(prefix="leancontext-codex-symlink-install-") as tmp:
            home = Path(tmp)
            (home / ".codex").mkdir(parents=True)
            (home / ".codex" / "config.toml").write_text('model = "gpt-5.4"\n')

            target = home / "other-plugin"
            target.mkdir()
            link = home / "plugins" / "leancontext"
            link.parent.mkdir(parents=True)
            link.symlink_to(target, target_is_directory=True)

            result = subprocess.run(
                [sys.executable, "install.py", "--codex"],
                cwd=REPO_ROOT,
                env={**os.environ, "HOME": str(home), "USERPROFILE": str(home)},
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("refusing to overwrite unmanaged path", result.stderr + result.stdout)
            self.assertTrue(link.is_symlink())

    def test_codex_uninstall_refuses_unmanaged_symlink(self):
        with tempfile.TemporaryDirectory(prefix="leancontext-codex-symlink-uninstall-") as tmp:
            home = Path(tmp)
            target = home / "other-plugin"
            target.mkdir()
            link = home / "plugins" / "leancontext"
            link.parent.mkdir(parents=True)
            link.symlink_to(target, target_is_directory=True)

            result = subprocess.run(
                [sys.executable, "uninstall.py", "--codex"],
                cwd=REPO_ROOT,
                env={**os.environ, "HOME": str(home), "USERPROFILE": str(home)},
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("refusing to remove unmanaged path", result.stderr + result.stdout)
            self.assertTrue(link.is_symlink())


if __name__ == "__main__":
    unittest.main()
