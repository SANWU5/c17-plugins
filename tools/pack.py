#!/usr/bin/env python3
"""C17 API 1/2 deterministic packaging. Standard library only; does not execute JS."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import re
import stat
import struct
import sys
import zipfile
from pathlib import Path, PurePosixPath

MAX_FILE = 256 * 1024
MAX_TOTAL = 1024 * 1024
MAX_FILES = 32
ROOT = Path(__file__).resolve().parents[1]
META_FIELDS = {"id", "name", "version", "versionCode", "apiVersion", "description", "author", "capabilities"}
PLUGIN_FIELDS = META_FIELDS | {"runtime"}
MANIFEST_FIELDS = PLUGIN_FIELDS | {"entry"}
ID_RE = re.compile(r"[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*\Z")
HEADER_RE = re.compile(r"^\s*var\s+plugin\s*=\s*", re.MULTILINE)
UI_RE = re.compile(r"^\s*plugin\s*\.\s*ui\s*=\s*", re.MULTILINE)
ALLOWED_EXT = {".js", ".md", ".txt"}


class Invalid(ValueError):
    pass


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Invalid("JSON 含重复字段：" + key)
        result[key] = value
    return result


def decode_json(data):
    try:
        return json.loads(data.decode("utf-8-sig"), object_pairs_hook=_pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(Invalid("JSON 数值无效：" + value)))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise Invalid("不是有效 UTF-8 JSON：" + str(error)) from error


def _text(obj, key, maximum, required=True):
    if not required and key not in obj:
        return
    value = obj.get(key)
    if not isinstance(value, str) or len(value) > maximum or "\0" in value or required and not value.strip():
        raise Invalid("元数据文字字段无效：" + key)


def validate_metadata(value, manifest=False, catalog=False):
    if not isinstance(value, dict) or set(value) - (MANIFEST_FIELDS if manifest else PLUGIN_FIELDS if not catalog else META_FIELDS):
        raise Invalid("元数据必须为对象且不能有未知字段")
    for key, maximum in (("id", 80), ("name", 80), ("version", 32)):
        _text(value, key, maximum)
    if len(value["id"]) < 3 or not ID_RE.fullmatch(value["id"]):
        raise Invalid("插件 ID 格式无效")
    _text(value, "description", 1024, False)
    _text(value, "author", 80, False)
    for key, low, high in (("versionCode", 1, 2147483647), ("apiVersion", 1, 2)):
        if type(value.get(key)) is not int or not low <= value[key] <= high:
            raise Invalid("元数据整数字段无效：" + key)
    runtime_api = value["apiVersion"] == 2
    caps = value.get("capabilities", [])
    allowed = ("settings", "systemui", "runtime") if runtime_api else ("settings", "systemui")
    if not isinstance(caps, list) or len(caps) > (len(allowed) if runtime_api else 2) or any(not isinstance(cap, str) or cap not in allowed for cap in caps) or len(set(caps)) != len(caps):
        raise Invalid("capabilities 不受支持或重复")
    if runtime_api and "runtime" not in caps:
        raise Invalid("API 2 插件必须声明 runtime 能力")
    if runtime_api and not catalog:
        runtime = value.get("runtime")
        if not isinstance(runtime, dict) or set(runtime) not in ({"entry"}, {"source"}):
            raise Invalid("API 2 必须声明 runtime.entry 或 runtime.source")
        if "entry" in runtime:
            _text(runtime, "entry", 4096)
            validate_path(runtime["entry"], 2)
            if PurePosixPath(runtime["entry"]).suffix != ".js":
                raise Invalid("runtime 入口必须为 .js")
        else:
            _text(runtime, "source", 2147483647)
    elif not runtime_api and ("runtime" in value or "runtime" in caps):
        raise Invalid("runtime 需要 API 2")
    if manifest:
        _text(value, "entry", 4096 if runtime_api else 128)
        validate_path(value["entry"], value["apiVersion"])
        if PurePosixPath(value["entry"]).suffix != ".js":
            raise Invalid("入口必须为 .js")


def validate_form(controls, api_version=1):
    """Validate the builder's literal form; the host still checks actual JS output."""
    if not isinstance(controls, list) or not controls or api_version == 1 and len(controls) > 64:
        raise Invalid("插件必须提供完整设置；API 1 的 ui 需包含 1–64 项控件，API 2 不设总项数配额")
    keys, editable = set(), 0
    def number(value):
        try:
            return type(value) in (int, float) and math.isfinite(value)
        except OverflowError:
            return False
    def primitive(value):
        return type(value) is bool or isinstance(value, str) and len(value) <= 4096 and "\0" not in value or number(value)
    for control in controls:
        if not isinstance(control, dict) or set(control) - {"type", "title", "description", "key", "default", "min", "max", "step", "unit", "options", "value"}:
            raise Invalid("插件控件必须为对象且不能包含未知字段")
        kind = control.get("type")
        if kind not in ("text", "switch", "slider", "input", "select", "button", "action", "status"):
            raise Invalid("不支持的插件控件类型")
        if kind in ("action", "status") and (api_version != 2 or set(control) - {"type", "title", "description", "key"}):
            raise Invalid("一次性操作与只读状态仅用于 API 2，不能包含持久配置字段")
        _text(control, "title", 120)
        _text(control, "description", 512, False)
        if "unit" in control:
            if kind != "slider":
                raise Invalid("只有滑块可以声明显示单位")
            _text(control, "unit", 16, False)
        if kind == "text":
            continue
        key = control.get("key")
        if not isinstance(key, str) or not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_.-]{0,63}", key) or key in ("constructor", "prototype") or key in keys:
            raise Invalid("插件配置 key 无效或重复")
        keys.add(key)
        if kind in ("action", "status"):
            continue
        if kind != "button":
            editable += 1
        default = control.get("default", False if kind == "switch" else control.get("min") if kind == "slider" else control.get("value", True) if kind == "button" else "")
        if kind == "select":
            options = control.get("options")
            if not isinstance(options, list) or not 1 <= len(options) <= 64:
                raise Invalid("选择控件必须声明 1–64 个选项")
            values = set()
            for option in options:
                if not isinstance(option, dict) or set(option) != {"value", "label"}:
                    raise Invalid("选择项必须包含 value 和 label")
                _text(option, "value", 128)
                _text(option, "label", 120)
                if option["value"] in values:
                    raise Invalid("选择项 value 重复")
                values.add(option["value"])
            default = control.get("default", options[0]["value"])
            if not isinstance(default, str) or default not in values:
                raise Invalid("默认配置不在选项中")
        if not primitive(default) or kind == "switch" and type(default) is not bool or kind == "input" and not isinstance(default, str):
            raise Invalid("插件配置默认值类型或内容无效")
        if kind == "slider":
            low, high, step = control.get("min"), control.get("max"), control.get("step", 1)
            if not all(number(value) for value in (low, high, step, default)) or not -100000 <= low < high <= 100000 or not 0 < step <= high-low or not low <= default <= high:
                raise Invalid("滑块范围、步长或默认值无效")
        if kind == "button" and not primitive(control.get("value", True)):
            raise Invalid("按钮值必须为文字、有限数字或布尔值")
    if editable == 0:
        raise Invalid("插件必须提供完整设置，至少声明一个开关、滑块、输入框或选择项；只有说明或按钮不符合规范")


def validate_source_form(source, api_version=1):
    matches = list(UI_RE.finditer(source))
    if len(matches) != 1:
        raise Invalid("标准构建器要求唯一的 plugin.ui = [严格 JSON 控件声明];，插件必须提供完整设置")
    try:
        controls, end = json.JSONDecoder(object_pairs_hook=_pairs, parse_constant=lambda value: (_ for _ in ()).throw(Invalid("JSON 数值无效：" + value))).raw_decode(source, matches[0].end())
    except json.JSONDecodeError as error:
        raise Invalid("标准构建器要求 plugin.ui 使用严格 JSON 数组；动态脚本请直接交宿主验证导入") from error
    if not source[end:].lstrip().startswith(";"):
        raise Invalid("plugin.ui 严格 JSON 数组后需要分号")
    validate_form(controls, api_version)


def validate_path(name, api_version=1):
    maximum = 4096 if api_version == 2 else 128
    if not isinstance(name, str) or not name or len(name) > maximum or "\\" in name or "\0" in name:
        raise Invalid("非法文件路径")
    path = PurePosixPath(name)
    if path.is_absolute() or ":" in name or any(part in ("", ".", "..") or part.endswith((".", " ")) for part in name.split("/")):
        raise Invalid("文件路径必须是无穿越的相对路径：" + name)
    if api_version == 1 and name not in ("LICENSE", "plugin.json") and path.suffix not in ALLOWED_EXT:
        raise Invalid("不支持的包内文件类型：" + name)


def validate_files(files):
    if not files or "plugin.json" not in files:
        raise Invalid("ZIP 根目录缺少 plugin.json")
    manifest = decode_json(files["plugin.json"])
    validate_metadata(manifest, True)
    api_version = manifest["apiVersion"]
    if api_version == 1 and (len(files) > MAX_FILES or sum(len(data) for data in files.values()) > MAX_TOTAL):
        raise Invalid("API 1 插件超过 32 项或 1MiB 总容量")
    normalized = set()
    for name, data in files.items():
        validate_path(name, api_version)
        canonical = name.lower()
        if canonical in normalized:
            raise Invalid("包内路径忽略大小写后重复：" + name)
        normalized.add(canonical)
        if api_version == 1 and len(data) > MAX_FILE:
            raise Invalid("单项文件超过 256KiB：" + name)
        if api_version == 1 or name == "plugin.json" or name == manifest["entry"] or name.endswith(".js"):
            try:
                text = data.decode("utf-8-sig")
            except UnicodeError as error:
                raise Invalid("插件脚本或说明必须为 UTF-8：" + name) from error
            if "\0" in text:
                raise Invalid("插件文本不能包含 NUL：" + name)
    if manifest["entry"] not in files:
        raise Invalid("入口文件不存在：" + manifest["entry"])
    runtime = manifest.get("runtime", {})
    if "entry" in runtime and runtime["entry"] not in files:
        raise Invalid("API 2 runtime 入口文件不存在：" + runtime["entry"])
    try:
        source = files[manifest["entry"]].decode("utf-8-sig")
    except UnicodeError as error:
        raise Invalid("入口脚本必须为 UTF-8") from error
    match = HEADER_RE.search(source)
    if not match:
        raise Invalid("标准构建器要求 var plugin = {严格 JSON 元数据}; 源码头；独立脚本可直接交应用导入")
    try:
        metadata, end = json.JSONDecoder(object_pairs_hook=_pairs).raw_decode(source, match.end())
    except json.JSONDecodeError as error:
        raise Invalid("plugin 元数据头必须是严格 JSON") from error
    if not source[end:].lstrip().startswith(";"):
        raise Invalid("plugin 元数据头后需要分号")
    validate_metadata(metadata)
    expected = {key: value for key, value in manifest.items() if key != "entry"}
    if metadata != expected:
        raise Invalid("manifest 与 JavaScript 元数据头不一致")
    if not re.search(r"\bC17\s*\.\s*define\s*\(", source):
        raise Invalid("脚本没有 C17.define 声明")
    validate_source_form(source, api_version)
    return manifest


def read_source(directory):
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise Invalid("源码目录不存在或为链接")
    manifest_path = directory / "plugin.json"
    if not manifest_path.is_file():
        raise Invalid("包根目录缺少 plugin.json")
    manifest = decode_json(manifest_path.read_bytes())
    validate_metadata(manifest, True)
    api_version = manifest["apiVersion"]
    files = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise Invalid("不接受符号链接：" + str(path))
        if path.is_file():
            name = path.relative_to(directory).as_posix()
            validate_path(name, api_version)
            if api_version == 1 and path.stat().st_size > MAX_FILE:
                raise Invalid("单项文件超过 256KiB：" + name)
            if api_version == 1 and len(files) >= MAX_FILES:
                raise Invalid("文件超过 32 项")
            files[name] = path.read_bytes()
    manifest = validate_files(files)
    files["plugin.json"] = json_bytes(manifest)
    return files, manifest


def archive_bytes(files):
    if len(files) >= 65535:
        raise Invalid("当前宿主支持经典 ZIP；文件数需能由非 ZIP64 档案表示")
    buffer = io.BytesIO()
    try:
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9, allowZip64=False) as archive:
            for name, data in sorted(files.items()):
                item = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                item.create_system = 3
                item.external_attr = (stat.S_IFREG | 0o644) << 16
                item.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(item, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    except zipfile.LargeZipFile as error:
        raise Invalid("当前宿主支持经典 ZIP，包超出档案格式范围") from error
    data = buffer.getvalue()
    inspect_archive(data)
    return data


def validate_zip_structure(data):
    """Match the host's classic ZIP format, including local/central header identity."""
    def field(offset, kind):
        size = struct.calcsize(kind)
        if offset < 0 or offset + size > len(data):
            raise Invalid("ZIP 文件头截断")
        return struct.unpack_from(kind, data, offset)[0]
    end = -1
    for position in range(len(data) - 22, max(-1, len(data) - 65558), -1):
        if field(position, "<I") == 0x06054b50 and position + 22 + field(position + 20, "<H") == len(data):
            end = position
            break
    if end < 0 or field(end + 4, "<H") or field(end + 6, "<H"):
        raise Invalid("ZIP 不完整或不支持分卷")
    count, size, offset = field(end + 10, "<H"), field(end + 12, "<I"), field(end + 16, "<I")
    if count == 65535 or size == 0xffffffff or offset == 0xffffffff:
        raise Invalid("当前宿主不支持 ZIP64，请重新打包为经典 ZIP")
    if not count or field(end + 8, "<H") != count or offset + size != end:
        raise Invalid("ZIP 目录无效")
    cursor, used_offsets = offset, set()
    for _ in range(count):
        if cursor + 46 > end or field(cursor, "<I") != 0x02014b50:
            raise Invalid("ZIP 中央目录无效")
        flags, method = field(cursor + 8, "<H"), field(cursor + 10, "<H")
        compressed, plain, local = field(cursor + 20, "<I"), field(cursor + 24, "<I"), field(cursor + 42, "<I")
        name_size, extra_size, comment_size = field(cursor + 28, "<H"), field(cursor + 30, "<H"), field(cursor + 32, "<H")
        if compressed == 0xffffffff or plain == 0xffffffff or local == 0xffffffff:
            raise Invalid("当前宿主不支持 ZIP64，请重新打包为经典 ZIP")
        if (flags & 1 or method not in (0, 8) or field(cursor + 34, "<H") or local + 30 > offset
                or local in used_offsets or cursor + 46 + name_size + extra_size + comment_size > end):
            raise Invalid("ZIP 不支持加密、分卷、重复偏移或无效压缩目录")
        used_offsets.add(local)
        if (field(local, "<I") != 0x04034b50 or field(local + 6, "<H") != flags
                or field(local + 8, "<H") != method or field(local + 26, "<H") != name_size):
            raise Invalid("ZIP 本地文件头与目录不一致")
        if local + 30 + name_size + field(local + 28, "<H") + compressed > offset:
            raise Invalid("ZIP 条目边界无效")
        if data[local + 30:local + 30 + name_size] != data[cursor + 46:cursor + 46 + name_size]:
            raise Invalid("ZIP 本地文件名与目录不一致")
        cursor += 46 + name_size + extra_size + comment_size
    if cursor != end:
        raise Invalid("ZIP 目录长度无效")


def inspect_archive(data):
    validate_zip_structure(data)
    files = {}
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            try:
                manifest = decode_json(archive.read("plugin.json"))
            except KeyError as error:
                raise Invalid("ZIP 根目录缺少 plugin.json") from error
            validate_metadata(manifest, True)
            api_version = manifest["apiVersion"]
            if api_version == 1 and (len(data) > MAX_TOTAL or len(archive.infolist()) > MAX_FILES):
                raise Invalid("API 1 ZIP 超过 1MiB 或 32 项")
            total = 0
            for item in archive.infolist():
                validate_path(item.filename, api_version)
                mode = item.external_attr >> 16
                if item.filename in files or item.is_dir() or stat.S_ISLNK(mode) or stat.S_IFMT(mode) not in (0, stat.S_IFREG) or item.flag_bits & 1:
                    raise Invalid("ZIP 含重复条目、目录、链接或加密条目")
                if item.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                    raise Invalid("ZIP 仅支持 stored/deflate 压缩")
                total += item.file_size
                if api_version == 1 and (item.file_size > MAX_FILE or total > MAX_TOTAL):
                    raise Invalid("ZIP 解压容量超限")
                if api_version == 1 and item.file_size > 65536 and item.file_size > max(1, item.compress_size) * 200:
                    raise Invalid("ZIP 条目压缩比超过 200")
                with archive.open(item) as stream:
                    content = stream.read() if api_version == 2 else stream.read(MAX_FILE + 1)
                if api_version == 1 and len(content) > MAX_FILE or len(content) != item.file_size:
                    raise Invalid("ZIP 条目大小无效")
                files[item.filename] = content
    except (zipfile.BadZipFile, NotImplementedError, RuntimeError) as error:
        raise Invalid("无效 ZIP：" + str(error)) from error
    return validate_files(files)


def build(directory, out):
    files, manifest = read_source(directory)
    data = archive_bytes(files)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    filename = f'{manifest["id"]}-{manifest["versionCode"]}.zip'
    checksum = hashlib.sha256(data).hexdigest()
    (out / filename).write_bytes(data)
    (out / (filename + ".sha256")).write_text(f"{checksum}  {filename}\n", encoding="utf-8", newline="\n")
    entry = {key: value for key, value in manifest.items() if key not in ("entry", "runtime")}
    entry.update(file=filename, sha256=checksum, size=len(data))
    return entry


def validate_catalog(catalog):
    allowed = {"schemaVersion", "apiVersion", "plugins", "name", "description", "updatedAt", "readmeUrl", "changesUrl"}
    if not isinstance(catalog, dict) or set(catalog) - allowed or type(catalog.get("schemaVersion")) is not int or catalog["schemaVersion"] != 1 or type(catalog.get("apiVersion")) is not int or catalog["apiVersion"] not in (1, 2):
        raise Invalid("目录格式或 API 版本无效")
    entries = catalog.get("plugins")
    if not isinstance(entries, list) or len(entries) > 128:
        raise Invalid("目录最多包含 128 个插件")
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) - (META_FIELDS | {"file", "sha256", "size"}):
            raise Invalid("目录条目有未知字段")
        validate_metadata({key: value for key, value in entry.items() if key in META_FIELDS}, catalog=True)
        if entry["apiVersion"] > catalog["apiVersion"]:
            raise Invalid("目录 API 版本不能低于插件 API 版本")
        if entry["id"] in seen:
            raise Invalid("索引包含重复插件 ID")
        seen.add(entry["id"])
        filename = entry.get("file")
        if not isinstance(filename, str) or not re.fullmatch(r"[a-z0-9_.-]+(?:/[a-z0-9_.-]+)*\.zip", filename) or any(part in (".", "..") for part in filename.split("/")):
            raise Invalid("目录 file 必须为安全相对 ZIP 路径")
        if not isinstance(entry.get("sha256"), str) or not re.fullmatch(r"[a-f0-9]{64}", entry["sha256"]):
            raise Invalid("目录 SHA-256 无效")
        maximum = MAX_TOTAL if entry["apiVersion"] == 1 else 2147483647
        if type(entry.get("size")) is not int or not 1 <= entry["size"] <= maximum:
            raise Invalid("目录 ZIP 大小无效")
    for key in allowed - {"schemaVersion", "apiVersion", "plugins"}:
        if key in catalog and (not isinstance(catalog[key], str) or len(catalog[key]) > 4096 or "\0" in catalog[key]):
            raise Invalid("目录说明字段无效：" + key)
    return catalog


def write_index(entries, out, metadata=None):
    ids = [entry["id"] for entry in entries]
    if len(set(ids)) != len(ids):
        raise Invalid("索引包含重复插件 ID")
    entries = sorted(entries, key=lambda value: value["id"])
    out = Path(out)
    catalog = dict(metadata or {})
    catalog.update(schemaVersion=1, apiVersion=max((entry["apiVersion"] for entry in entries), default=1), plugins=entries)
    validate_catalog(catalog)
    data = json_bytes(catalog)
    (out / "index.json").write_bytes(data)
    sums = [f'{entry["sha256"]}  {entry["file"]}' for entry in entries]
    sums.append(hashlib.sha256(data).hexdigest() + "  index.json")
    (out / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8", newline="\n")


def publish(directory, repository):
    """Prepare a reviewed package and local catalog; never commit, push or publish remotely."""
    directory, repository = Path(directory).resolve(), Path(repository).resolve()
    for templates in (ROOT / "templates", repository / "templates"):
        try:
            directory.relative_to(templates.resolve())
        except ValueError:
            continue
        raise Invalid("教学模板不能直接发布；请复制到自己的开发目录、修改身份并完成审查")
    files, manifest = read_source(directory)
    if "LICENSE" not in files or "README.md" not in files or not manifest.get("author", "").strip():
        raise Invalid("正式分发需要作者、包内 LICENSE 与 README.md 来源/适配说明")
    index = repository / "index.json"
    catalog = validate_catalog(decode_json(index.read_bytes())) if index.exists() else {"schemaVersion": 1, "apiVersion": 1, "plugins": []}
    data = archive_bytes(files)
    checksum = hashlib.sha256(data).hexdigest()
    previous = next((item for item in catalog["plugins"] if item["id"] == manifest["id"]), None)
    if previous is not None and (manifest["versionCode"] < previous["versionCode"] or manifest["versionCode"] == previous["versionCode"] and checksum != previous["sha256"]):
        raise Invalid("禁止降级或替换同版本的不同内容，请增加 versionCode")
    if previous is None and len(catalog["plugins"]) >= 128:
        raise Invalid("目录已达 128 个插件上限")
    entry = build(directory, repository / "packages")
    entry["file"] = "packages/" + entry["file"]
    entries = [item for item in catalog["plugins"] if item["id"] != entry["id"]] + [entry]
    write_index(entries, repository, {key: value for key, value in catalog.items() if key != "plugins"})
    return entry


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    for name in ("lint", "build", "build-all", "inspect", "catalog", "publish"):
        sub = subs.add_parser(name)
        if name == "build-all":
            sub.add_argument("source", type=Path, nargs="?", default=ROOT / "templates")
        else:
            sub.add_argument("source", type=Path)
        if name in ("build", "build-all"):
            sub.add_argument("--out", type=Path, default=Path("dist"))
        if name == "publish":
            sub.add_argument("--repository", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        if args.command == "lint":
            files, manifest = read_source(args.source)
            archive_bytes(files)
            print("结构通过：" + manifest["id"] + "；JavaScript 语义仍由 C17 校验")
        elif args.command == "inspect":
            manifest = inspect_archive(args.source.read_bytes())
            print("ZIP 结构通过：" + manifest["id"])
        elif args.command == "catalog":
            catalog = validate_catalog(decode_json(args.source.read_bytes()))
            print("目录通过：" + str(len(catalog["plugins"])) + " 个插件")
        elif args.command == "publish":
            entry = publish(args.source, args.repository)
            print("已准备本地发行包与目录：" + entry["file"] + "；尚未提交或推送")
        else:
            sources = [args.source] if args.command == "build" else sorted(path for path in args.source.iterdir() if path.is_dir())
            if not sources:
                raise Invalid("没有插件源码")
            # Validate every package and duplicate ID before producing a partial index.
            seen = set()
            for source in sources:
                files, manifest = read_source(source)
                archive_bytes(files)
                if manifest["id"] in seen:
                    raise Invalid("重复插件 ID：" + manifest["id"])
                seen.add(manifest["id"])
            entries = [build(source, args.out) for source in sources]
            print(f"已生成 {len(entries)} 个本地开发包与校验和；未更新公开目录")
        return 0
    except (Invalid, OSError, ValueError) as error:
        print("失败：" + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
