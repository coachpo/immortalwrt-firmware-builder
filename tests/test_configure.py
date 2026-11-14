import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("configure", ROOT / "scripts/configure.py")
configure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(configure)


class ConfigureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.tree = Path(self.temp.name)
        (self.tree / "scripts").mkdir()
        (self.tree / "feeds.conf.default").write_text("src-git luci https://example.org/luci\n")
        (self.tree / "scripts/projectsmirrors.json").write_text(json.dumps({
            **{key: ["https://mirrors.tencent.com/source"] for key in configure.PROJECT_MIRRORS},
            "@OPENWRT": ["https://sources.openwrt.org"],
        }))
        libressl = self.tree / "tools/libressl"
        libressl.mkdir(parents=True)
        (libressl / "Makefile").write_text(
            "PKG_SOURCE_URL:=https://mirrors.tencent.com/OpenBSD/LibreSSL/ \\\n"
            "\thttps://ftp.openbsd.org/pub/OpenBSD/LibreSSL\n\nPKG_HASH:=unchanged\n"
        )
        (self.tree / "scripts/download.pl").write_text(r'''use strict;
use warnings;
my @mirrors;
sub projectsmirrors {
    my ($project, $path) = @_;
    die "unexpected project" unless $project eq '@GITHUB';
    push @mirrors, "https://raw.githubusercontent.com/$path";
}
my $mirror = $ARGV[0];
if ($mirror eq 'unused') {
    die "unused";
	} elsif ($mirror =~ /^\@GITHUB\/(.+)$/) {
        push @mirrors, "https://raw.gitmirror.com/$1";
        projectsmirrors '@GITHUB', $1;
	} elsif ($mirror =~ /^\@GNU\/(.+)$/) {
        die "unused";
}
print join("\n", @mirrors), "\n";
''')

    def test_github_downloads_resolve_directly_without_proxy_defaults(self):
        configure.prepare_source(self.tree)
        output = subprocess.run([
            "perl", str(self.tree / "scripts/download.pl"), "@GITHUB/example/repo/main/file.txt",
        ], text=True, capture_output=True, check=True).stdout
        self.assertEqual(output.splitlines(), [
            "https://raw.githubusercontent.com/example/repo/main/file.txt",
        ])

    def test_prepare_is_idempotent_and_preserves_unrelated_configuration(self):
        feeds = self.tree / "feeds.conf"
        feeds.write_text("# custom feeds\nsrc-link local /packages\n"
                         "src-git vantage https://example.org/old\n")
        (self.tree / "files").mkdir()
        (self.tree / "files/custom").write_text("user overlay")
        configure.prepare_source(self.tree)
        first = {path.relative_to(self.tree): path.read_bytes()
                 for path in self.tree.rglob("*") if path.is_file()}
        configure.prepare_source(self.tree)
        second = {path.relative_to(self.tree): path.read_bytes()
                  for path in self.tree.rglob("*") if path.is_file()}
        self.assertEqual(first, second)
        self.assertEqual(feeds.read_text().splitlines(), [
            "# custom feeds", "src-link local /packages", configure.VANTAGE_FEED,
        ])
        self.assertEqual((self.tree / "files/custom").read_text(), "user overlay")
        self.assertTrue(os.access(self.tree / "files/etc/uci-defaults/zzzz-vantage-theme", os.X_OK))
        mirrors = json.loads((self.tree / "scripts/projectsmirrors.json").read_text())
        for key, urls in configure.PROJECT_MIRRORS.items():
            self.assertEqual(mirrors[key], urls)
        self.assertEqual(mirrors["@OPENWRT"], ["https://sources.openwrt.org"])
        self.assertEqual((self.tree / "tools/libressl/Makefile").read_text(),
                         "PKG_SOURCE_URL:=https://ftp.openbsd.org/pub/OpenBSD/LibreSSL\n\n"
                         "PKG_HASH:=unchanged\n")

    def test_configure_orders_feeds_before_defconfig(self):
        with patch.object(configure.subprocess, "run") as run:
            configure.configure(self.tree, ccache=True)
        self.assertEqual([call.args[0] for call in run.call_args_list], [
            ["./scripts/feeds", "update", "-a"],
            ["./scripts/feeds", "install", "-a"],
            ["make", "defconfig"],
        ])
        self.assertIn("CONFIG_CCACHE=y", (self.tree / ".config").read_text())
        self.assertTrue(all(call.kwargs == {"cwd": self.tree, "check": True}
                            for call in run.call_args_list))

    def test_failed_feed_update_stops_configuration(self):
        with patch.object(configure.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "feeds")) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                configure.configure(self.tree)
        self.assertEqual(run.call_count, 1)
        self.assertFalse((self.tree / ".config").exists())

    def test_missing_theme_after_defconfig_is_an_error(self):
        def run(command, **kwargs):
            if command == ["make", "defconfig"]:
                seed = (ROOT / "tr3000/seed.config").read_text()
                (self.tree / ".config").write_text(seed.replace(
                    "CONFIG_PACKAGE_luci-theme-vantage=y",
                    "# CONFIG_PACKAGE_luci-theme-vantage is not set",
                ))
        with patch.object(configure.subprocess, "run", side_effect=run):
            with self.assertRaisesRegex(ValueError, "did not retain CONFIG_PACKAGE_luci-theme-vantage=y"):
                configure.configure(self.tree)

    def test_china_defaults_cannot_be_reenabled_by_dependencies(self):
        config = self.tree / ".config"
        seed = (ROOT / "tr3000/seed.config").read_text()
        for value in ("y", "m"):
            with self.subTest(value=value):
                config.write_text(seed + f"\nCONFIG_PACKAGE_default-settings-chn={value}\n")
                with self.assertRaisesRegex(ValueError, "China-specific"):
                    configure.check_config(config)


class ThemeDefaultsTests(unittest.TestCase):
    def test_theme_selection_and_uci_failure(self):
        # A command double checks the shell control flow, not real UCI or LuCI.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            uci = path / "uci"
            uci.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$UCI_LOG"\n'
                           '[ "$1" != "$FAIL_UCI" ]\n')
            uci.chmod(0o755)
            for failure, expected in (("", 0), ("set", 1), ("commit", 1)):
                with self.subTest(failure=failure):
                    log = path / f"log-{failure}"
                    result = subprocess.run([
                        "sh", str(ROOT / "tr3000/files/etc/uci-defaults/zzzz-vantage-theme"),
                    ], env={**os.environ, "PATH": f"{path}:{os.environ['PATH']}",
                            "UCI_LOG": str(log), "FAIL_UCI": failure})
                    self.assertEqual(result.returncode, expected)
                    operations = log.read_text().splitlines()
                    self.assertEqual(operations[0], "set luci.main.mediaurlbase=/luci-static/vantage")
                    self.assertEqual(len(operations), 1 if failure == "set" else 2)
                    if failure != "set":
                        self.assertEqual(operations[1], "commit luci")


if __name__ == "__main__":
    unittest.main()
