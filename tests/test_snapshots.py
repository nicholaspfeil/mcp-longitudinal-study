"""Tests for the snapshot layout change of session 16 (scan/snapshots.py).

    python -m unittest discover tests
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scan import snapshots
from scan.snapshots import iter_lines, list_snapshots, write_snapshot

RECORDS = [{"observed_at": "t", "entry": {"server": {"name": f"s{i}"}}} for i in range(50)]


class SnapshotLayout(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_round_trip_splits_into_parts_and_loses_nothing(self):
        # Force tiny parts so a 50-record test exercises the splitting.
        with mock.patch.object(snapshots, "PART_MAX_BYTES", 300):
            out = write_snapshot(iter(RECORDS), self.dir, "20990101T000000Z")
        parts = sorted(out.glob("part-*.jsonl"))
        self.assertGreater(len(parts), 1)
        self.assertTrue(all(p.stat().st_size <= 300 for p in parts))
        self.assertEqual([json.loads(l) for l in iter_lines(out)], RECORDS)

    def test_no_part_is_ever_over_the_limit_or_empty(self):
        with mock.patch.object(snapshots, "PART_MAX_BYTES", 300):
            out = write_snapshot(iter(RECORDS), self.dir, "20990101T000000Z")
        for p in out.glob("part-*.jsonl"):
            self.assertGreater(p.stat().st_size, 0)

    def test_old_files_and_new_dirs_list_together_in_time_order(self):
        (self.dir / "registry-20260928T000000Z.jsonl").write_text("{}\n")
        write_snapshot(iter(RECORDS), self.dir, "20261116T000000Z")
        (self.dir / "registry-20261109T000000Z.jsonl").write_text("{}\n")
        names = [p.name for p in list_snapshots(self.dir)]
        self.assertEqual(names, [
            "registry-20260928T000000Z.jsonl",
            "registry-20261109T000000Z.jsonl",
            "registry-20261116T000000Z",
        ])

    def test_unfinished_write_is_not_a_snapshot(self):
        (self.dir / "registry-20261116T000000Z.partial").mkdir()
        self.assertEqual(list_snapshots(self.dir), [])

    def test_old_single_file_still_reads(self):
        path = self.dir / "registry-20260928T000000Z.jsonl"
        path.write_text("".join(json.dumps(r) + "\n" for r in RECORDS))
        self.assertEqual([json.loads(l) for l in iter_lines(path)], RECORDS)


if __name__ == "__main__":
    unittest.main()
