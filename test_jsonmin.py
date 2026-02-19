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


# ─── RESULTS ─────────────────────────────────────────────────────

print(f"\n{'=' * 50}")
print(f"Results: {PASS} passed, {FAIL} failed")
print(f"{'=' * 50}\n")
sys.exit(1 if FAIL > 0 else 0)
