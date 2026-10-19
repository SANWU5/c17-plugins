import copy
import hashlib
import importlib.util
import io
import json
import stat
import tempfile
import shutil
import unittest
import warnings
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("c17_pack", ROOT / "tools" / "pack.py")
pack = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pack)


class PackagingTests(unittest.TestCase):
    def files(self):
        return pack.read_source(ROOT / "templates" / "clock-seconds")[0]

    def mutate_manifest(self, files, **values):
        manifest = pack.decode_json(files["plugin.json"])
        manifest.update(values)
        files["plugin.json"] = pack.json_bytes(manifest)
        return files

    def zip_bytes(self, entries):
        buffer = io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                for name, value in entries:
                    archive.writestr(name, value)
        return buffer.getvalue()

    def test_all_developer_templates_build_and_inspect(self):
        for source in sorted((ROOT / "templates").iterdir()):
            with self.subTest(example=source.name):
                files, manifest = pack.read_source(source)
                self.assertEqual(manifest, pack.inspect_archive(pack.archive_bytes(files)))

    def test_identical_files_in_different_order_make_identical_zip(self):
        files = self.files()
        self.assertEqual(pack.archive_bytes(files), pack.archive_bytes(dict(reversed(list(files.items())))))
        with zipfile.ZipFile(io.BytesIO(pack.archive_bytes(files))) as archive:
            self.assertEqual(sorted(files), archive.namelist())
            self.assertTrue(all(item.date_time == (1980, 1, 1, 0, 0, 0) for item in archive.infolist()))

    def test_catalog_hashes_match_actual_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            entries = [pack.build(source, out) for source in sorted((ROOT / "templates").iterdir())]
            pack.write_index(entries, out)
            catalog = pack.decode_json((out / "index.json").read_bytes())
            self.assertEqual(3, len(catalog["plugins"]))
            for item in catalog["plugins"]:
                data = (out / item["file"]).read_bytes()
                self.assertEqual(item["sha256"], hashlib.sha256(data).hexdigest())
                self.assertEqual(item["size"], len(data))
            for line in (out / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
                digest, name = line.split("  ", 1)
                self.assertEqual(digest, hashlib.sha256((out / name).read_bytes()).hexdigest())

    def test_manifest_source_identity_mismatch_is_rejected(self):
        with self.assertRaisesRegex(pack.Invalid, "不一致"):
            pack.validate_files(self.mutate_manifest(self.files(), name="不匹配"))

    def test_unknown_manifest_field_is_rejected(self):
        with self.assertRaises(pack.Invalid):
            pack.validate_files(self.mutate_manifest(self.files(), network=True))

    def test_boolean_is_not_a_version_integer(self):
        with self.assertRaises(pack.Invalid):
            pack.validate_files(self.mutate_manifest(self.files(), versionCode=True))

    def test_invalid_api_version_is_rejected(self):
        with self.assertRaises(pack.Invalid):
            pack.validate_files(self.mutate_manifest(self.files(), apiVersion=2))

    def test_duplicate_capabilities_are_rejected(self):
        with self.assertRaises(pack.Invalid):
            pack.validate_files(self.mutate_manifest(self.files(), capabilities=["settings", "settings"]))

    def test_duplicate_json_fields_are_rejected(self):
        with self.assertRaisesRegex(pack.Invalid, "重复"):
            pack.decode_json(b'{"id":"one","id":"two"}')

    def test_missing_entry_is_rejected(self):
        files = self.files()
        del files["main.js"]
        with self.assertRaisesRegex(pack.Invalid, "不存在"):
            pack.validate_files(files)

    def test_unsafe_paths_and_extensions_are_rejected(self):
        for name in ("../main.js", "/main.js", "a/../b.js", "a\\b.js", "C:/main.js", "a//b.js", "a/./b.js", "payload.dex", chr(0) + ".js"):
            with self.subTest(name=name), self.assertRaises(pack.Invalid):
                pack.validate_path(name)

    def test_oversized_source_is_rejected_before_packaging(self):
        files = self.files()
        files["main.js"] = b"x" * (pack.MAX_FILE + 1)
        with self.assertRaises(pack.Invalid):
            pack.validate_files(files)

    def test_too_many_files_are_rejected(self):
        files = self.files()
        files.update({f"extra-{number}.txt": b"x" for number in range(33)})
        with self.assertRaises(pack.Invalid):
            pack.validate_files(files)

    def test_duplicate_zip_entry_is_rejected(self):
        files = self.files()
        data = self.zip_bytes(list(files.items()) + [("main.js", files["main.js"])])
        with self.assertRaisesRegex(pack.Invalid, "重复"):
            pack.inspect_archive(data)

    def test_zip_traversal_is_rejected(self):
        with self.assertRaises(pack.Invalid):
            pack.inspect_archive(self.zip_bytes(list(self.files().items()) + [("../bad.js", b"bad")]))

    def test_case_insensitive_duplicate_paths_are_rejected(self):
        with self.assertRaisesRegex(pack.Invalid, "重复"):
            pack.inspect_archive(self.zip_bytes(list(self.files().items()) + [("MAIN.js", b"bad")]))

    def test_only_root_plugin_json_is_accepted(self):
        for name in ("extra.json", "nested/plugin.json", "main.JS", "README.MD", "trailing./good.js", "trailing /good.js"):
            with self.subTest(name=name), self.assertRaises(pack.Invalid):
                pack.validate_path(name)

    def test_every_packaged_text_file_must_be_utf8_without_nul(self):
        for data in (bytes([255]), b"text" + bytes([0])):
            with self.subTest(data=data), self.assertRaises(pack.Invalid):
                pack.inspect_archive(self.zip_bytes(list(self.files().items()) + [("bad.txt", data)]))

    def test_unsupported_zip_compression_is_rejected(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_BZIP2) as archive:
            for name, data in self.files().items():
                archive.writestr(name, data)
        with self.assertRaisesRegex(pack.Invalid, "压缩"):
            pack.inspect_archive(buffer.getvalue())

    def test_zip_symlink_is_rejected(self):
        link = zipfile.ZipInfo("link.js")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        data = self.zip_bytes(list(self.files().items()) + [(link, b"main.js")])
        with self.assertRaisesRegex(pack.Invalid, "链接"):
            pack.inspect_archive(data)

    def test_zip_directory_entry_is_rejected(self):
        with self.assertRaises(pack.Invalid):
            pack.inspect_archive(self.zip_bytes(list(self.files().items()) + [("folder/", b"")]))

    def test_zip_high_compression_ratio_is_rejected(self):
        with self.assertRaisesRegex(pack.Invalid, "压缩比"):
            pack.inspect_archive(self.zip_bytes(list(self.files().items()) + [("large.txt", b"0" * 100000)]))

    def test_duplicate_catalog_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as out:
            entry = pack.build(ROOT / "templates" / "clock-seconds", out)
            with self.assertRaises(pack.Invalid):
                pack.write_index([entry, copy.deepcopy(entry)], out)

    def test_standard_source_header_is_required_without_executing_code(self):
        files = self.files()
        files["main.js"] = b"throw new Error('must never execute'); C17.define({});"
        with self.assertRaisesRegex(pack.Invalid, "源码头"):
            pack.validate_files(files)

    def test_public_catalog_is_deliberately_empty(self):
        catalog = pack.validate_catalog(pack.decode_json((ROOT / "index.json").read_bytes()))
        self.assertEqual([], catalog["plugins"])
        self.assertEqual("C17 扩展插件", catalog["name"])
        self.assertEqual("https://github.com/SANWU5/c17-plugins/blob/main/README.md", catalog["readmeUrl"])
        self.assertEqual("https://github.com/SANWU5/c17-plugins/blob/main/CHANGELOG.md", catalog["changesUrl"])
        self.assertEqual([], list((ROOT / "packages").glob("*.zip")))

    def test_default_developer_build_does_not_publish_catalog(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary) / "dist"
            before = (ROOT / "index.json").read_bytes()
            self.assertEqual(0, pack.main(["build-all", "--out", str(out)]))
            self.assertEqual(3, len(list(out.glob("*.zip"))))
            self.assertFalse((out / "index.json").exists())
            self.assertEqual(before, (ROOT / "index.json").read_bytes())

    def test_direct_template_publish_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary, self.assertRaisesRegex(pack.Invalid, "教学模板"):
            pack.publish(ROOT / "templates" / "clock-seconds", Path(temporary))

    def test_explicit_publish_requires_license_and_uses_package_relative_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "development"
            shutil.copytree(ROOT / "templates" / "clock-seconds", source)
            repository = base / "repository"
            with self.assertRaisesRegex(pack.Invalid, "LICENSE"):
                pack.publish(source, repository)
            shutil.copyfile(ROOT / "LICENSE", source / "LICENSE")
            entry = pack.publish(source, repository)
            self.assertTrue(entry["file"].startswith("packages/"))
            data = (repository / entry["file"]).read_bytes()
            self.assertEqual(entry["sha256"], hashlib.sha256(data).hexdigest())
            self.assertEqual([entry], pack.validate_catalog(pack.decode_json((repository / "index.json").read_bytes()))["plugins"])
            # Same immutable content is safe to prepare again; changed same-version content is not.
            self.assertEqual(entry, pack.publish(source, repository))
            with (source / "README.md").open("a", encoding="utf-8") as output:
                output.write("\nChanged publication content\n")
            with self.assertRaisesRegex(pack.Invalid, "同版本"):
                pack.publish(source, repository)

    def test_catalog_rejects_absolute_traversal_query_and_fragment_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            item = pack.build(ROOT / "templates" / "clock-seconds", Path(temporary))
            for name in ("https://bad.example/a.zip", "../a.zip", "/a.zip", "packages/a.zip?q=x", "packages/a.zip#x", "packages\\a.zip"):
                with self.subTest(name=name), self.assertRaises(pack.Invalid):
                    pack.validate_catalog({"schemaVersion": 1, "apiVersion": 1, "plugins": [dict(item, file=name)]})


if __name__ == "__main__":
    unittest.main()
