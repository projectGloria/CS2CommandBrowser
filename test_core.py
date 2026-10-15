from dataclasses import replace
import csv
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from core import Entry, ScanError, alphabetical_group, atomic_json, check_config, compare, entries_from_schema, export_entries, export_grouped, group_alphabetically, load_snapshot, resolve_game, run_scan


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.game = self.root / "A game with spaces" / "game"
        for name in ("bin/win64/tier0.dll", "csgo/bin/win64/client.dll"):
            path = self.game / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"test fixture")
        (self.game / "csgo/steam.inf").write_text("ClientVersion=123\nPatchVersion=test\n")
        self.extractor = self.root / "offline.exe"
        self.extractor.write_bytes(b"test fixture")
        self.storage = self.root / "results"
        self.example = {"convars": [{"name": "test_text", "default": 'a "quoted" value; // text', "type": "string", "help": "Çalışır\nSecond line", "flags": ["archive"], "modules": ["client"]}],
                        "commands": [{"name": "test_command", "flags": ["release"], "modules": ["server"]}]}

    def fake_run(self, argv, **kwargs):
        output = Path(argv[1])
        (output / "schemas.json").write_text(json.dumps(self.example), encoding="utf-8")
        for name in ("convars.txt", "commands.txt"):
            (output / name).write_text("fixture", encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0)

    def test_manual_paths_accept_three_documented_levels(self):
        for path in (self.game.parent, self.game, self.game / "bin/win64"):
            self.assertEqual(resolve_game(str(path)), self.game.resolve())
        self.assertEqual(resolve_game('"' + str(self.game) + '"'), self.game.resolve())

    def test_missing_path_is_not_searched_for(self):
        with self.assertRaises(ScanError):
            resolve_game("")
        with self.assertRaises(ScanError):
            resolve_game(self.root / "not the installation")

    def test_schema_preserves_unicode_strings_and_missing_description(self):
        entries = entries_from_schema(self.example)
        text = next(entry for entry in entries if entry.kind == "Variable")
        self.assertEqual(text.default, 'a "quoted" value; // text')
        self.assertEqual(text.description, "Çalışır\nSecond line")
        self.assertEqual(next(entry for entry in entries if entry.kind == "Command").description, "")

    def test_absent_default_is_not_replaced_with_zero(self):
        self.example["convars"][0].pop("default")
        entry = next(entry for entry in entries_from_schema(self.example) if entry.kind == "Variable")
        self.assertIsNone(entry.default)

    def test_incomplete_or_duplicate_schema_fails(self):
        with self.assertRaises(ScanError):
            entries_from_schema({"convars": [], "commands": []})
        self.example["convars"].append(dict(self.example["convars"][0]))
        with self.assertRaises(ScanError):
            entries_from_schema(self.example)

    def test_comparison_includes_removed_and_description_only_changes(self):
        a = Entry("one", "Variable", default="1", description="Old")
        b = Entry("two", "Command")
        changes = compare([a, b], [replace(a, description="New"), Entry("three", "Command")])
        self.assertEqual(changes, {"Variable:one": "Changed", "Command:two": "Removed", "Command:three": "Added"})

    def test_export_json_and_csv_preserve_text_and_escape_formula_names(self):
        entries = entries_from_schema(self.example) + [Entry("+attack", "Command")]
        for suffix in ("json", "csv", "txt"):
            export_entries(self.root / f"output.{suffix}", entries)
        saved = json.loads((self.root / "output.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["entries"][1]["description"], "Çalışır\nSecond line")
        with (self.root / "output.csv").open(encoding="utf-8-sig", newline="") as source:
            rows = list(csv.reader(source))
        self.assertEqual(rows[-1][0], "'+attack")
        self.assertEqual(rows[2][2], "Çalışır\nSecond line")

    def test_successful_scan_uses_copies_and_publishes_complete_snapshot(self):
        with patch("core.subprocess.run", side_effect=self.fake_run) as process:
            result = run_scan(str(self.game), self.extractor, self.storage)
        metadata, entries = load_snapshot(result)
        self.assertEqual(metadata["version"]["ClientVersion"], "123")
        self.assertEqual(len(entries), 2)
        cwd = Path(process.call_args.kwargs["cwd"])
        self.assertNotEqual(cwd, self.game / "bin/win64")
        self.assertTrue(cwd.is_relative_to(self.storage))
        self.assertEqual((self.game / "bin/win64/tier0.dll").read_bytes(), b"test fixture")
        self.assertEqual(Path(json.loads((self.storage / "latest.json").read_text())["snapshot"]), result)

    def test_failed_scan_keeps_last_good_results(self):
        with patch("core.subprocess.run", side_effect=self.fake_run):
            good = run_scan(str(self.game), self.extractor, self.storage)
        with patch("core.subprocess.run", return_value=subprocess.CompletedProcess([], 1)):
            with self.assertRaises(ScanError):
                run_scan(str(self.game), self.extractor, self.storage)
        pointer = json.loads((self.storage / "latest.json").read_text())
        self.assertEqual(Path(pointer["snapshot"]), good)

    def test_game_update_during_scan_does_not_publish(self):
        def update_mid_scan(argv, **kwargs):
            result = self.fake_run(argv, **kwargs)
            (self.game / "csgo/steam.inf").write_text("ClientVersion=124\n")
            return result
        with patch("core.subprocess.run", side_effect=update_mid_scan):
            with self.assertRaises(ScanError):
                run_scan(str(self.game), self.extractor, self.storage)
        self.assertFalse((self.storage / "latest.json").exists())

    def test_output_inside_game_is_rejected(self):
        with self.assertRaises(ScanError):
            run_scan(str(self.game), self.extractor, self.game / "results")
        self.assertFalse((self.game / "results").exists())

    def test_timeout_preserves_previous_pointer_and_releases_lock(self):
        def timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired("test", 1)
        with patch("core.subprocess.run", side_effect=timeout):
            with self.assertRaises(ScanError):
                run_scan(str(self.game), self.extractor, self.storage)
        with patch("core.subprocess.run", side_effect=self.fake_run):
            self.assertTrue(run_scan(str(self.game), self.extractor, self.storage).exists())

    def test_config_checker_does_not_label_alias_as_removed(self):
        entries = [Entry("cl_drawhud", "Variable", flags=("cheat",)), Entry("alias", "Command"), Entry("bind", "Command")]
        findings = check_config('alias mine "something"\nmine\ncl_drawhud 0\n+forward\nbind h "cl_drawhud 0"', entries)
        self.assertEqual([finding["line"] for finding in findings], [3, 4])
        self.assertIn("does not prove removal", findings[1]["detail"])

    def test_two_simultaneous_scans_are_rejected(self):
        def nested(argv, **kwargs):
            with self.assertRaisesRegex(ScanError, "Another scan"):
                run_scan(str(self.game), self.extractor, self.storage)
            return self.fake_run(argv, **kwargs)
        with patch("core.subprocess.run", side_effect=nested):
            self.assertTrue(run_scan(str(self.game), self.extractor, self.storage).exists())

    def test_export_keeps_removed_status(self):
        entry = Entry("removed", "Command")
        path = self.root / "changed.csv"
        export_entries(path, [entry], changes={entry.key: "Removed"})
        with path.open(encoding="utf-8-sig", newline="") as source:
            rows = list(csv.DictReader(source))
        self.assertEqual(rows[0]["Change"], "Removed")

    def test_alphabetical_groups_handle_input_prefixes_and_symbols(self):
        names = ["+attack", "-Attack", "_fov", "cl_drawhud", "3d_test", "!debug", "z_last"]
        entries = [Entry(name, "Command") for name in names]
        groups = group_alphabetically(entries)
        self.assertEqual(list(groups), ["A", "C", "F", "Z", "#"])
        self.assertEqual({entry.name for entry in groups["A"]}, {"+attack", "-Attack"})
        self.assertEqual(alphabetical_group(""), "#")
        self.assertEqual(alphabetical_group("ı_test"), "I")

    def test_grouped_json_is_complete_sorted_and_preserves_descriptions(self):
        entries = [Entry("beta", "Variable", description="Çalışır\nLine two", default=""),
                   Entry("Alpha", "Command"), Entry("apple", "Variable", default="-120"), Entry("+attack", "Command")]
        output = self.root / "alphabet.zip"
        export_grouped(output, entries, "json", {"version": {"ClientVersion": "123"}}, {"Command:Alpha": "Removed"})
        with zipfile.ZipFile(output) as archive:
            self.assertEqual(set(archive.namelist()), {"A.json", "B.json", "INDEX.md", "manifest.json"})
            a = json.loads(archive.read("A.json"))
            b = json.loads(archive.read("B.json"))
            self.assertEqual([entry["name"] for entry in a["entries"]], ["+attack", "Alpha", "apple"])
            self.assertEqual(a["entries"][1]["change"], "Removed")
            self.assertEqual(b["entries"][0]["description"], "Çalışır\nLine two")
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(sum(group["count"] for group in manifest["groups"]), len(entries))
            self.assertEqual(manifest["entry_count"], len(entries))

    def test_every_grouped_format_contains_all_entries(self):
        entries = [Entry("a_name", "Variable", description="line one\nline two", default="1"), Entry("z_name", "Command")]
        for extension in ("txt", "csv", "json", "md"):
            path = self.root / f"groups-{extension}.zip"
            export_grouped(path, entries, extension)
            with zipfile.ZipFile(path) as archive:
                self.assertIn("a_name", archive.read("A."+extension).decode("utf-8-sig"))
                self.assertIn("z_name", archive.read("Z."+extension).decode("utf-8-sig"))
                self.assertIsNone(archive.testzip())

    def test_grouped_export_failure_preserves_existing_file(self):
        output = self.root / "existing.zip"
        output.write_bytes(b"prior export")
        with patch("core.export_entries", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                export_grouped(output, [Entry("one", "Command")])
        self.assertEqual(output.read_bytes(), b"prior export")
        self.assertEqual(list(self.root.glob("existing.zip.*.tmp")), [])

    def test_empty_or_invalid_grouped_export_creates_no_archive(self):
        path = self.root / "empty.zip"
        with self.assertRaises(ValueError):
            export_grouped(path, [])
        with self.assertRaises(ValueError):
            export_grouped(path, [Entry("one", "Command")], "exe")
        self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
