"""Tests for the session-17 safety changes to scan/run_scan.py.

    python -m unittest discover tests

None of these touch the network or clone anything.
"""

from __future__ import annotations

import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scan import run_scan


class LeftoverSweep(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_removes_leftovers_including_read_only_git_files(self):
        clone = self.root / f"{run_scan.TEMP_PREFIX}abc" / "repo" / ".git" / "objects"
        clone.mkdir(parents=True)
        obj = clone / "pack.idx"
        obj.write_text("x")
        os.chmod(obj, stat.S_IREAD)          # how git leaves its object files
        self.assertEqual(run_scan.sweep_leftovers(self.root), 0)
        self.assertFalse((self.root / f"{run_scan.TEMP_PREFIX}abc").exists())

    def test_leaves_other_folders_alone(self):
        (self.root / "someone-elses-folder").mkdir()
        run_scan.sweep_leftovers(self.root)
        self.assertTrue((self.root / "someone-elses-folder").exists())

    def test_reports_what_it_could_not_delete(self):
        (self.root / f"{run_scan.TEMP_PREFIX}stuck").mkdir()
        with mock.patch.object(run_scan.shutil, "rmtree", side_effect=PermissionError):
            self.assertEqual(run_scan.sweep_leftovers(self.root), 1)


class WhereItRuns(unittest.TestCase):
    def test_full_scan_refuses_to_run_off_actions(self):
        env = {k: v for k, v in os.environ.items() if k != "GITHUB_ACTIONS"}
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch("sys.argv", ["run_scan"]), \
             mock.patch.object(run_scan, "select_repos") as select:
            with self.assertRaises(SystemExit):
                run_scan.main()
            select.assert_not_called()       # refused before reading the work list

    def test_safe_list_parses(self):
        urls = run_scan.read_repos_file(Path("tests/safe_repos.txt"))
        self.assertTrue(urls)
        self.assertTrue(all(u.startswith("https://github.com/") for u in urls))


if __name__ == "__main__":
    unittest.main()
