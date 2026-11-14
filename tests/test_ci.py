import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("ci", ROOT / "scripts/ci.py")
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        for name in ci.FIRMWARE_FILES:
            (self.source / name).write_bytes(f"firmware: {name}".encode())

    def test_complete_firmware_survives_upload_and_release_staging(self):
        (self.source / "unrelated.bin").write_bytes(b"not a TR3000 release asset")
        upload = self.root / "upload"
        release = self.root / "release"
        ci.collect_firmware(self.source, upload)
        ci.collect_firmware(upload, release)
        self.assertEqual(set(file.name for file in release.iterdir()), set(ci.FIRMWARE_FILES))
        for name in ci.FIRMWARE_FILES:
            self.assertEqual((release / name).read_bytes(), (self.source / name).read_bytes())

    def test_each_missing_or_empty_required_file_prevents_staging(self):
        for name in ci.FIRMWARE_FILES:
            for state in ("missing", "empty"):
                with self.subTest(file=name, state=state):
                    path = self.source / name
                    contents = path.read_bytes()
                    if state == "missing":
                        path.unlink()
                    else:
                        path.write_bytes(b"")
                    destination = self.root / "invalid"
                    with self.assertRaisesRegex(ValueError, name):
                        ci.collect_firmware(self.source, destination)
                    self.assertFalse(destination.exists())
                    path.write_bytes(contents)

    def test_collect_cli_fails_for_incomplete_output(self):
        (self.source / ci.FIRMWARE_FILES[0]).unlink()
        result = subprocess.run([
            "python3", str(ROOT / "scripts/ci.py"), "collect",
            str(self.source), str(self.root / "invalid"),
        ], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn(ci.FIRMWARE_FILES[0], result.stderr)

    def test_existing_staging_directory_cannot_leak_stale_assets(self):
        destination = self.root / "existing"
        destination.mkdir()
        (destination / "stale.bin").write_bytes(b"old asset")
        with self.assertRaises(FileExistsError):
            ci.collect_firmware(self.source, destination)
        self.assertEqual([file.name for file in destination.iterdir()], ["stale.bin"])


class CacheTests(unittest.TestCase):
    def test_new_runs_and_retries_refresh_keys_but_share_restore_prefixes(self):
        environment = {
            "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64",
            "GITHUB_RUN_ID": "100", "GITHUB_RUN_ATTEMPT": "1",
            "IMMORTALWRT_REF": "openwrt/25.12", "CACHE_EPOCH": "v1",
        }
        seed = ROOT / "tr3000/seed.config"
        original = ci.cache_outputs(environment, seed)
        for change in ({"GITHUB_RUN_ID": "101"}, {"GITHUB_RUN_ATTEMPT": "2"}):
            refreshed = ci.cache_outputs({**environment, **change}, seed)
            for kind in ("ccache", "dl"):
                self.assertNotEqual(original[f"{kind}_key"], refreshed[f"{kind}_key"])
                self.assertEqual(original[f"{kind}_prefix"], refreshed[f"{kind}_prefix"])
                self.assertTrue(refreshed[f"{kind}_key"].startswith(original[f"{kind}_prefix"]))
        self.assertNotEqual(original["ccache_key"], original["dl_key"])
        self.assertIn("openwrt_25.12", original["ccache_key"])

    def test_seed_and_epoch_change_specific_prefix_platform_separates_caches(self):
        environment = {"RUNNER_OS": "Linux", "RUNNER_ARCH": "X64",
                       "GITHUB_RUN_ID": "100", "GITHUB_RUN_ATTEMPT": "1"}
        with tempfile.TemporaryDirectory() as directory:
            seed = Path(directory) / "seed.config"
            seed.write_text("CONFIG_FIRST=y\n")
            original = ci.cache_outputs(environment, seed)
            seed.write_text("CONFIG_SECOND=y\n")
            changed = ci.cache_outputs(environment, seed)
        self.assertNotEqual(original["dl_prefix"], changed["dl_prefix"])
        self.assertEqual(original["dl_ref_prefix"], changed["dl_ref_prefix"])
        epoch = ci.cache_outputs({**environment, "CACHE_EPOCH": "v2"}, ROOT / "tr3000/seed.config")
        self.assertIn("-v2-", epoch["ccache_prefix"])
        arm = ci.cache_outputs({**environment, "RUNNER_ARCH": "ARM64"}, ROOT / "tr3000/seed.config")
        self.assertNotEqual(original["dl_target_prefix"], arm["dl_target_prefix"])


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tree = self.root / "source"
        # Reuse existing local commits; tests neither create commits nor use the network.
        subprocess.run(["git", "clone", "--quiet", "--shared", str(ROOT), str(self.tree)], check=True)
        self.feeds = self.tree / "feeds"
        self.feeds.mkdir()
        subprocess.run(["git", "clone", "--quiet", "--shared", str(ROOT), str(self.feeds / "vantage")], check=True)
        (self.tree / "feeds.conf").write_text("src-git vantage https://example.org/vantage\n")

    def test_records_actual_revisions_config_and_applicable_source_patch(self):
        config = b"CONFIG_PACKAGE_luci-theme-vantage=y\n"
        (self.tree / ".config").write_bytes(config)
        readme = self.tree / "README.md"
        readme.write_text(readme.read_text() + "\nsource customization\n")
        destination = self.root / "provenance"
        ci.record_provenance(ROOT, self.tree, destination, {
            "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "2",
            "GITHUB_REPOSITORY": "example/builder", "IMMORTALWRT_REF": "master",
            "CONFIGURATION_OUTCOME": "success", "COMPILATION_OUTCOME": "success",
        })
        info = json.loads((destination / "build-info.json").read_text())
        expected = ci.git_output(self.tree, "rev-parse", "HEAD").strip()
        self.assertEqual(info["immortalwrt_commit"], expected)
        self.assertEqual(info["builder_commit"], ci.git_output(ROOT, "rev-parse", "HEAD").strip())
        self.assertEqual(info["feeds"], {"vantage": expected})
        self.assertTrue(info["config_available"])
        self.assertEqual(info["run_url"], "https://github.com/example/builder/actions/runs/123")
        self.assertEqual((destination / "firmware.config").read_bytes(), config)
        self.assertEqual((destination / "seed.config").read_bytes(), (ROOT / "tr3000/seed.config").read_bytes())
        self.assertEqual((destination / "feeds.conf").read_bytes(), (self.tree / "feeds.conf").read_bytes())
        subprocess.run(["git", "-C", str(self.tree), "apply", "--check", "--reverse",
                        str(destination / "source.patch")], check=True)
        ci.verify_provenance(destination, info["builder_commit"])
        for name in (*ci.PROVENANCE_FILES, "source.patch"):
            with self.subTest(missing=name):
                file = destination / name
                saved = self.root / "saved"
                file.rename(saved)
                with self.assertRaisesRegex(ValueError, "Missing or empty"):
                    ci.verify_provenance(destination, info["builder_commit"])
                saved.rename(file)

    def test_release_rejects_wrong_commit_or_unsuccessful_build_provenance(self):
        (self.tree / ".config").write_text("CONFIG_PACKAGE_luci-theme-vantage=y\n")
        destination = self.root / "ready"
        ci.record_provenance(ROOT, self.tree, destination, {
            "CONFIGURATION_OUTCOME": "success", "COMPILATION_OUTCOME": "success",
        })
        metadata = destination / "build-info.json"
        original = json.loads(metadata.read_text())
        expected = original["builder_commit"]
        ci.verify_provenance(destination, expected)
        self.assertFalse(original["source_modified"])
        with self.assertRaisesRegex(ValueError, "does not match"):
            ci.verify_provenance(destination, "different-builder-commit")
        for stage in ("configuration_outcome", "compilation_outcome"):
            with self.subTest(stage=stage):
                metadata.write_text(json.dumps({**original, stage: "failure"}))
                with self.assertRaisesRegex(ValueError, "unsuccessful"):
                    ci.verify_provenance(destination, expected)
        metadata.write_text(json.dumps({**original, "feeds": {"vantage": None}}))
        with self.assertRaisesRegex(ValueError, "unresolved revision"):
            ci.verify_provenance(destination, expected)

    def test_partial_configuration_still_records_available_evidence(self):
        subprocess.run(["git", "init", "--quiet", str(self.feeds / "incomplete")], check=True)
        destination = self.root / "partial"
        ci.record_provenance(ROOT, self.tree, destination, {})
        info = json.loads((destination / "build-info.json").read_text())
        self.assertFalse(info["config_available"])
        self.assertIsNone(info["feeds"]["incomplete"])
        self.assertFalse((destination / "firmware.config").exists())
        self.assertTrue((destination / "seed.config").is_file())


if __name__ == "__main__":
    unittest.main()
