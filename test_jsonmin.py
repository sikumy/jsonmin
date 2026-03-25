#!/usr/bin/env python3
"""Exhaustive test suite for jsonmin.py — 50 edge cases."""

import json
import re
import subprocess
import sys

PASS = 0
FAIL = 0


def run_jsonmin(data, extra_args=None):
    cmd = [sys.executable, "jsonmin.py"] + (extra_args or [])
    return subprocess.run(
        cmd,
        input=json.dumps(data),
        capture_output=True,
        text=True,
    )


def assert_output_contains(name, data, expected, extra_args=None):
    global PASS, FAIL
    result = run_jsonmin(data, extra_args)
    output = result.stdout + result.stderr
    if expected in output:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}")
        print(f"        expected to find: {expected!r}")
        print(f"        got: {output!r}")


def assert_output_not_contains(name, data, unexpected, extra_args=None):
    global PASS, FAIL
    result = run_jsonmin(data, extra_args)
    output = result.stdout + result.stderr
    if unexpected not in output:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}")
        print(f"        did NOT expect: {unexpected!r}")
        print(f"        got: {output!r}")


def assert_no_double_dots(name, data, extra_args=None):
    global PASS, FAIL
    result = run_jsonmin(data, extra_args)
    output = result.stdout
    if ".." not in output:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}")
        lines = [l for l in output.split("\n") if ".." in l]
        print(f"        double dots found in: {lines}")


def run_jq_path_test(name, data, extra_args=None):
    """Verify every path from --paths actually works in jq."""
    global PASS, FAIL
    result = run_jsonmin(data, ["--paths"])
    if result.returncode != 0:
        FAIL += 1
        print(f"  FAIL  {name} (jsonmin crashed)")
        return

    lines = result.stdout.strip().split("\n")
    paths = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("Root:") or line.startswith("Use with"):
            continue
        # Path ends before the last whitespace-separated type token
        # Types are: string, number, boolean, null, array(N)
        m = re.match(r'^(.+?)\s{2,}(\S+)\s*$', line)
        if m:
            path = m.group(1).strip()
            if path.startswith(".") or path.startswith("["):
                paths.append(path)

    if not paths:
        FAIL += 1
        print(f"  FAIL  {name} (no paths extracted)")
        return

    json_str = json.dumps(data)
    valid = 0
    for path in paths:
        jq_result = subprocess.run(
            ["jq", path],
            input=json_str,
            capture_output=True,
            text=True,
        )
        if jq_result.returncode == 0:
            valid += 1
        else:
            print(f"        jq failed for path: {path}")
            print(f"        stderr: {jq_result.stderr.strip()}")

    if valid == len(paths):
        PASS += 1
        print(f"  PASS  {name} ({valid} paths valid in jq)")
    else:
        FAIL += 1
        print(f"  FAIL  {name} ({valid}/{len(paths)} paths valid)")


# ─── 1. PRIMITIVE ROOT VALUES ───────────────────────────────────

print("\n=== 1. PRIMITIVE ROOT VALUES ===")
assert_output_contains("root string", "hello", "string")
assert_output_contains("root number int", 42, "number")
assert_output_contains("root number float", 3.14, "number")
assert_output_contains("root boolean true", True, "boolean")
assert_output_contains("root boolean false", False, "boolean")
assert_output_contains("root null", None, "null")


# ─── 2. EMPTY STRUCTURES ────────────────────────────────────────

print("\n=== 2. EMPTY STRUCTURES ===")
assert_output_contains("empty object", {}, "object")
assert_output_contains("empty array", [], "array")
assert_output_contains("object with empty object", {"a": {}}, "{}")
assert_output_contains("object with empty array", {"a": []}, "array")


# ─── 3. KEYS REQUIRING QUOTING ──────────────────────────────────

print("\n=== 3. KEYS REQUIRING QUOTING ===")
assert_output_contains("key with hyphen", {"my-key": 1}, '.\"my-key\"')
assert_output_contains("key with space", {"my key": 1}, '.\"my key\"')
assert_output_contains("key with dot", {"a.b": 1}, '.\"a.b\"')
assert_output_contains("key starting with number", {"3abc": 1}, '.\"3abc\"')
assert_output_contains("key with double quote", {'a"b': 1}, '.\"a\\"b\"')
assert_output_contains("key empty string", {"": 1}, '.\"\"')
assert_output_contains("key unicode", {"café": 1}, '.\"café\"')
assert_output_contains("key with backslash", {"a\\b": 1}, '."a\\\\b"')


# ─── 4. ARRAY EDGE CASES ────────────────────────────────────────

print("\n=== 4. ARRAY EDGE CASES ===")
assert_output_contains("array of primitives (strings)", ["a", "b", "c"], "string")
assert_output_contains("array of primitives (numbers)", [1, 2, 3], "number")
assert_output_contains("array of primitives (booleans)", [True, False], "boolean")
assert_output_contains("array of primitives (nulls)", [None, None], "null")
assert_output_contains("array single element object", [{"id": 1}], "id")
assert_output_contains("array mixed primitives", [1, "a", True, None], "mixed")
assert_output_contains("array of arrays", [[1, 2], [3, 4]], "array")
assert_output_contains("array nested arrays", [[[1]]], "array")
assert_output_contains("single primitive in array", [42], "number")


# ─── 5. DEEP NESTING ────────────────────────────────────────────

print("\n=== 5. DEEP NESTING ===")
deep = {"a": {"b": {"c": {"d": {"e": "deep"}}}}}
assert_output_contains("5-level deep nesting", deep, ".a.b.c.d.e")
assert_output_contains("deeply nested array", {"x": [{"y": [{"z": 1}]}]}, ".x")


# ─── 6. SPECIAL VALUES ──────────────────────────────────────────

print("\n=== 6. SPECIAL VALUES ===")
assert_output_contains("large number", {"n": 99999999999999999}, "number")
assert_output_contains("negative number", {"n": -42}, "number")
assert_output_contains("float zero", {"n": 0.0}, "number")
assert_output_contains("empty string value", {"s": ""}, "string")
assert_output_contains(
    "long string value",
    {"s": "a" * 200},
    "...",
)


# ─── 7. MIXED OBJECT SHAPES (like SharePoint) ───────────────────

print("\n=== 7. MIXED OBJECTS SHAPES (like SharePoint) ===")
sharepoint_like = [
    {"Key": "Title", "Value": "Hello", "ValueType": "Edm.String"},
    {"Key": "Id", "Value": "42", "ValueType": "Edm.Int64"},
    42,
    {"Score": 100},
    {"Key": "Author", "Value": "Admin", "ValueType": "Edm.String"},
]
assert_output_contains("SharePoint-like mixed array", sharepoint_like, "shape")


# ─── 8. --paths MODE ────────────────────────────────────────────

print("\n=== 8. --paths MODE ===")
assert_output_contains("paths simple object", {"a": 1, "b": "x"}, ".a", ["--paths"])
assert_output_contains("paths nested", {"a": {"b": 1}}, ".a.b", ["--paths"])
assert_output_contains("paths array", {"items": [{"id": 1}]}, ".items[]", ["--paths"])
assert_output_contains("paths quoted key", {"my-key": 1}, '.\"my-key\"', ["--paths"])
assert_output_contains("paths root array", [{"id": 1}], ".[]", ["--paths"])
assert_output_contains("paths root primitive", "hello", "Root:", ["--paths"])


# ─── 9. JQ PATH VALIDATION ──────────────────────────────────────

print("\n=== 9. JQ PATH VALIDATION ===")
run_jq_path_test("jq: simple object", {"name": "Alice", "age": 30, "active": True})
run_jq_path_test("jq: array of objects", [{"id": 1, "value": "a"}, {"id": 2, "value": "b"}])
run_jq_path_test("jq: nested arrays", {"data": [{"items": [1, 2, 3]}]})
run_jq_path_test("jq: quoted keys", {"another key": {"sub-field": "x"}})
run_jq_path_test(
    "jq: root array mixed",
    [{"a": 1}, {"a": 2, "b": 3}, 42],
)


# ─── 10. PATH CORRECTNESS (no double dots) ──────────────────────

print("\n=== 10. PATH CORRECTNESS (no double dots) ===")
assert_no_double_dots("no double dots in structure", {"data": {"items": [{"id": 1}]}})
assert_no_double_dots("no double dots in paths", {"data": {"items": [{"id": 1}]}}, ["--paths"])
assert_no_double_dots("no double dots root array", [{"a": {"b": 1}}])
assert_no_double_dots("no double dots root array paths", [{"a": {"b": 1}}], ["--paths"])


# ─── 11. JSONL / CONCATENATED JSON ──────────────────────────────

def run_jsonmin_raw(raw_input, extra_args=None):
    cmd = [sys.executable, "jsonmin.py"] + (extra_args or [])
    return subprocess.run(
        cmd,
        input=raw_input,
        capture_output=True,
        text=True,
    )


def assert_raw_output_contains(name, raw_input, expected, extra_args=None):
    global PASS, FAIL
    result = run_jsonmin_raw(raw_input, extra_args)
    output = result.stdout + result.stderr
    if expected in output:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}")
        print(f"        expected to find: {expected!r}")
        print(f"        got: {output!r}")


def assert_raw_exits_ok(name, raw_input, extra_args=None):
    global PASS, FAIL
    result = run_jsonmin_raw(raw_input, extra_args)
    if result.returncode == 0:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}")
        print(f"        expected exit 0, got {result.returncode}")
        print(f"        stderr: {result.stderr!r}")


def assert_raw_output_not_contains(name, raw_input, unexpected, extra_args=None):
    global PASS, FAIL
    result = run_jsonmin_raw(raw_input, extra_args)
    output = result.stdout + result.stderr
    if unexpected not in output:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}")
        print(f"        did NOT expect: {unexpected!r}")
        print(f"        got: {output!r}")


print("\n=== 11. JSONL / CONCATENATED JSON ===")

# Multiple JSON objects separated by newlines (JSON Lines)
jsonl_objects = '{"a":1}\n{"b":2}\n{"c":3}\n'
assert_raw_exits_ok("jsonl: multiple objects parse ok", jsonl_objects)
assert_raw_output_contains("jsonl: detected as multiple values", jsonl_objects, "3 JSON values")
assert_raw_output_contains("jsonl: shows structure", jsonl_objects, "array")

# JSONL with --paths should work
assert_raw_exits_ok("jsonl: --paths works", jsonl_objects, ["--paths"])

# Mixed types in JSONL
jsonl_mixed = '42\n"hello"\n{"key":"val"}\n'
assert_raw_exits_ok("jsonl: mixed types parse ok", jsonl_mixed)
assert_raw_output_contains("jsonl: mixed types detected", jsonl_mixed, "3 JSON values")

# Concatenated JSON (no newlines between values)
concat_json = '{"a":1}{"b":2}'
assert_raw_exits_ok("concatenated json: parse ok", concat_json)
assert_raw_output_contains("concatenated json: detected", concat_json, "2 JSON values")

# Single valid JSON still works normally (no JSONL message)
single_json = '{"a": 1}'
assert_raw_output_not_contains("single json: no JSONL message", single_json, "JSON values")

# JSONL with blank lines between values
jsonl_blanks = '{"a":1}\n\n{"b":2}\n\n'
assert_raw_exits_ok("jsonl: blank lines tolerated", jsonl_blanks)

# JSONL paths should NOT use array indexing — jq handles JSONL natively
jsonl_for_jq = '{"name":"Alice","age":30}\n{"name":"Bob","age":25}\n'
assert_raw_output_contains("jsonl: paths use .field not .[].field", jsonl_for_jq, ".name", ["--paths"])
assert_raw_output_not_contains("jsonl: no .[].name in paths", jsonl_for_jq, ".[].name", ["--paths"])
assert_raw_output_not_contains("jsonl: no .[] root path", jsonl_for_jq, ".[]", ["--paths"])

# JSONL jq hint should NOT suggest wrapping in array
assert_raw_output_not_contains("jsonl: jq hint no array", jsonl_for_jq, ".[", ["--paths"])

# Verify JSONL paths actually work with jq on the original JSONL stream
def run_jq_on_jsonl(name, jsonl_input, extra_args=None):
    global PASS, FAIL
    result = run_jsonmin_raw(jsonl_input, ["--paths"])
    if result.returncode != 0:
        FAIL += 1
        print(f"  FAIL  {name} (jsonmin crashed)")
        return

    lines = result.stdout.strip().split("\n")
    paths = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("Root:") or line.startswith("Use with"):
            continue
        m = re.match(r'^(.+?)\s{2,}(\S+)\s*$', line)
        if m:
            path = m.group(1).strip()
            if path.startswith(".") or path.startswith("["):
                paths.append(path)

    if not paths:
        FAIL += 1
        print(f"  FAIL  {name} (no paths extracted)")
        return

    valid = 0
    for path in paths:
        jq_result = subprocess.run(
            ["jq", path],
            input=jsonl_input,
            capture_output=True,
            text=True,
        )
        if jq_result.returncode == 0:
            valid += 1
        else:
            print(f"        jq failed for path: {path}")
            print(f"        stderr: {jq_result.stderr.strip()}")

    if valid == len(paths):
        PASS += 1
        print(f"  PASS  {name} ({valid} paths valid in jq)")
    else:
        FAIL += 1
        print(f"  FAIL  {name} ({valid}/{len(paths)} paths valid)")


run_jq_on_jsonl("jq: jsonl paths work natively", jsonl_for_jq)

# JSONL with different shapes should not produce duplicate paths
jsonl_shapes = '{"name":"Alice","age":30}\n{"name":"Bob","age":25,"extra":"x"}\n'
result_shapes = run_jsonmin_raw(jsonl_shapes, ["--paths"])
shape_lines = [l.strip() for l in result_shapes.stdout.strip().split("\n")
               if l.strip() and not l.strip().startswith("Root:") and not l.strip().startswith("Use with")]
shape_paths = []
for line in shape_lines:
    m = re.match(r'^(.+?)\s{2,}(\S+)\s*$', line)
    if m:
        shape_paths.append(m.group(1).strip())
if len(shape_paths) == len(set(shape_paths)):
    PASS += 1
    print(f"  PASS  jsonl: no duplicate paths ({len(shape_paths)} unique)")
else:
    FAIL += 1
    dupes = [p for p in shape_paths if shape_paths.count(p) > 1]
    print(f"  FAIL  jsonl: no duplicate paths (found dupes: {set(dupes)})")

# Regular array should still use .[].field syntax (not affected by JSONL fix)
assert_output_contains("regular array: uses .[].field", [{"id": 1}, {"id": 2}], ".[].id", ["--paths"])

# JSONL structure view should also show correct paths (not .[].field)
jsonl_struct = '{"x":1}\n{"x":2}\n'
assert_raw_output_not_contains("jsonl: structure no .[].x", jsonl_struct, ".[].x")
assert_raw_output_contains("jsonl: structure uses .x", jsonl_struct, ".x")


# ─── 12. --debug FLAG FOR PARSE ERRORS ──────────────────────────

# ─── 13. JQ MULTI-FIELD HINT ────────────────────────────────────

print("\n=== 13. JQ MULTI-FIELD HINT ===")

# --paths output must show a multi-field example with {f1, f2} syntax
assert_output_contains("hint: multi-field object syntax", {"a": 1, "b": "x"}, "{field1, field2}", ["--paths"])

# --paths output must show comma-separated values syntax
assert_output_contains("hint: comma-separated values syntax", {"a": 1, "b": "x"}, ".field1, .field2", ["--paths"])

# --paths output must show select/filter example
assert_output_contains("hint: select filter example", {"a": 1, "b": "x"}, "select(", ["--paths"])

# JSONL --paths should also have the multi-field hint
jsonl_hint = '{"a":1,"b":"x"}\n{"a":2,"b":"y"}\n'
assert_raw_output_contains("jsonl hint: multi-field syntax", jsonl_hint, "{field1, field2}", ["--paths"])
assert_raw_output_contains("jsonl hint: select filter", jsonl_hint, "select(", ["--paths"])


# ─── 12. --debug FLAG FOR PARSE ERRORS ──────────────────────────

print("\n=== 12. --debug FLAG FOR PARSE ERRORS ===")

# Truly invalid JSON should show context with --debug
bad_json = '{"key": value_without_quotes}'
result_bad = run_jsonmin_raw(bad_json, ["--debug"])
assert_raw_output_contains("debug: shows error detail", bad_json, "invalid JSON", ["--debug"])
assert_raw_output_contains("debug: shows context snippet", bad_json, "value_without_quotes", ["--debug"])

# --debug with valid JSON should not change output
assert_raw_exits_ok("debug: valid json still works", '{"a":1}', ["--debug"])

# --debug with JSONL should work fine
assert_raw_exits_ok("debug: jsonl still works", jsonl_objects, ["--debug"])

# Without --debug, invalid JSON shows simple error (no snippet)
result_no_debug = run_jsonmin_raw(bad_json)
assert_raw_output_contains("no debug: shows simple error", bad_json, "invalid JSON")
assert_raw_output_not_contains("no debug: no context snippet", bad_json, "value_without_quotes")

# --debug with truncated JSON
truncated = '{"key": "val'
assert_raw_output_contains("debug: truncated json hint", truncated, "invalid JSON", ["--debug"])


# ─── RESULTS ─────────────────────────────────────────────────────

print(f"\n{'=' * 50}")
print(f"Results: {PASS} passed, {FAIL} failed")
print(f"{'=' * 50}\n")
sys.exit(1 if FAIL > 0 else 0)
