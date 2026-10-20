"""Optional JSON Schema parity checks; the packer itself remains standard-library only."""
import copy
import json
import unittest
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except ImportError:
    Draft202012Validator = None

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(Draft202012Validator is None, "Install jsonschema to check the published schemas")
class SchemaParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schemas = {name: json.loads((ROOT / "schema" / (name + ".schema.json")).read_text(encoding="utf-8"))
                       for name in ("manifest", "descriptor", "catalog")}
        cls.validators = {name: Draft202012Validator(schema) for name, schema in cls.schemas.items()}

    def metadata(self, api_version=2):
        value = {"id": "example.complete.plugin", "name": "Complete plugin", "version": "2.1.0_beta.002",
                 "versionCode": 7, "apiVersion": api_version, "capabilities": ["runtime"] if api_version == 2 else ["settings"]}
        if api_version == 2:
            value["runtime"] = {"entry": "runtime.js"}
        return value

    def descriptor(self, api_version=2, count=1):
        return dict(self.metadata(api_version), ui=[{"type": "switch", "key": f"option_{index}", "title": f"Option {index}"}
                                                   for index in range(count)], settings={}, hooks=[])

    def entry(self, api_version=2, **changed):
        value = {key: value for key, value in self.metadata(api_version).items() if key != "runtime"}
        value.update(file="packages/complete.zip", sha256="a" * 64, size=1048577 if api_version == 2 else 1024)
        value.update(changed)
        return value

    def test_all_schemas_are_valid_2020_12(self):
        for name, schema in self.schemas.items():
            with self.subTest(schema=name):
                Draft202012Validator.check_schema(schema)

    def test_api1_and_api2_are_valid_across_three_schemas(self):
        for api in (1, 2):
            cases = {"manifest": dict(self.metadata(api), entry="main.js"), "descriptor": self.descriptor(api),
                     "catalog": {"schemaVersion": 1, "apiVersion": api, "plugins": [self.entry(api)]}}
            for name, value in cases.items():
                with self.subTest(api=api, schema=name):
                    self.validators[name].validate(value)

    def test_api2_requires_runtime_and_declared_capability(self):
        for name, value in (("manifest", dict(self.metadata(), entry="main.js")), ("descriptor", self.descriptor())):
            for field in ("runtime", "capabilities"):
                changed = copy.deepcopy(value)
                del changed[field]
                with self.subTest(schema=name, missing=field):
                    self.assertFalse(self.validators[name].is_valid(changed))
            for runtime in ({"source": ""}, {"source": "   "}, {"entry": "../bad.js"}, {"entry": "x.js", "source": "code"}):
                with self.subTest(schema=name, runtime=runtime):
                    self.assertFalse(self.validators[name].is_valid(dict(value, runtime=runtime)))
            self.validators[name].validate(dict(value, runtime={"source": "C17.log('inline');"}))

    def test_api2_form_and_package_size_do_not_inherit_api1_quotas(self):
        self.validators["descriptor"].validate(self.descriptor(2, 80))
        self.assertFalse(self.validators["descriptor"].is_valid(self.descriptor(1, 80)))
        self.validators["manifest"].validate(dict(self.metadata(), entry="nested/" * 20 + "main.js"))
        self.assertFalse(self.validators["manifest"].is_valid(dict(self.metadata(1), entry="nested/" * 20 + "main.js")))
        for api in (1, 2):
            catalog = {"schemaVersion": 1, "apiVersion": api, "plugins": [self.entry(api, size=1048577)]}
            self.assertEqual(api == 2, self.validators["catalog"].is_valid(catalog))

    def test_catalog_rejects_private_script_and_downgraded_api(self):
        catalog = {"schemaVersion": 1, "apiVersion": 2, "plugins": [self.entry()]}
        self.assertFalse(self.validators["catalog"].is_valid(dict(catalog, apiVersion=1)))
        for field, value in (("runtime", {"source": "code"}), ("entry", "runtime.js"), ("ui", []), ("hooks", [])):
            with self.subTest(field=field):
                self.assertFalse(self.validators["catalog"].is_valid(dict(catalog, plugins=[self.entry(**{field: value})])))
        self.assertFalse(self.validators["catalog"].is_valid(dict(catalog, plugins=[self.entry(capabilities=[])])))

    def test_api1_cannot_declare_runtime_and_forms_must_be_editable(self):
        self.assertFalse(self.validators["manifest"].is_valid(dict(self.metadata(1), entry="main.js", runtime={"source": "code"})))
        for api in (1, 2):
            for ui in ([], [{"type": "text", "title": "Only description"}], [{"type": "button", "title": "Only button", "key": "action"}]):
                with self.subTest(api=api, ui=ui):
                    self.assertFalse(self.validators["descriptor"].is_valid(dict(self.descriptor(api), ui=ui)))

    def test_runtime_actions_and_status_are_not_saved_state(self):
        controls = [{"type": "switch", "title": "Enabled", "key": "enabled"},
                    {"type": "action", "title": "Capture", "key": "capture"},
                    {"type": "status", "title": "Saved time", "key": "saved_at"}]
        self.validators["descriptor"].validate(dict(self.descriptor(), ui=controls))
        self.assertFalse(self.validators["descriptor"].is_valid(dict(self.descriptor(1), ui=controls)))
        self.assertFalse(self.validators["descriptor"].is_valid(dict(self.descriptor(), ui=controls[1:])))
        for kind in ("action", "status"):
            for key, value in (("default", True), ("value", 1), ("options", []), ("min", 0),
                               ("max", 1), ("step", 1), ("unit", "%")):
                with self.subTest(kind=kind, field=key):
                    invalid = controls[:1] + [{"type": kind, "title": "Runtime", "key": "runtime", key: value}]
                    self.assertFalse(self.validators["descriptor"].is_valid(dict(self.descriptor(), ui=invalid)))


if __name__ == "__main__":
    unittest.main()
