#!/usr/bin/env python3
"""
jsonmin - Reveal the structure of any JSON file.

Shows the skeleton of a JSON document: keys, types, nesting depth,
array lengths, sample values, and ready-to-use jq paths.
"""

import argparse
import json
import re
import sys
from pathlib import Path

MAX_SAMPLE_LENGTH = 60
MAX_ARRAY_PREVIEW = 3
JQ_SAFE_KEY = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def setup_colors():
    use_color = sys.stdout.isatty()
    codes = {
        "RESET": "\033[0m",
        "BOLD": "\033[1m",
        "DIM": "\033[2m",
        "RED": "\033[31m",
        "GREEN": "\033[32m",
        "YELLOW": "\033[33m",
        "BLUE": "\033[34m",
        "MAGENTA": "\033[35m",
        "CYAN": "\033[36m",
    }
    if not use_color:
        return {k: "" for k in codes}
    return codes


C = setup_colors()

TYPE_COLORS = {
    "string": C["GREEN"],
    "number": C["YELLOW"],
    "boolean": C["MAGENTA"],
    "null": C["RED"],
    "object": C["CYAN"],
    "array": C["BLUE"],
}


def jq_key(key):
    if JQ_SAFE_KEY.match(key):
        return key
    escaped = key.replace('\\', '\\\\').replace('"', '\\"')
    return f'"{ escaped }"'


def jq_child_path(parent, key):
    return f"{parent}.{jq_key(key)}"


def jq_index_path(parent, index=None):
    base = parent if parent else "."
    if index is None:
        return f"{base}[]"
    return f"{base}[{index}]"


def jq_display(path):
    return path if path else "."


def json_type(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def truncate(text, max_len=MAX_SAMPLE_LENGTH):
    text = str(text)
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def colored(text, color):
    return f"{color}{text}{C['RESET']}"


def type_label(value):
    t = json_type(value)
    label = colored(t, TYPE_COLORS.get(t, C["RESET"]))
    if t == "array":
        label += colored(f"[{len(value)}]", C["DIM"])
    if t == "object":
        label += colored(f"{{{len(value)} keys}}", C["DIM"])
    return label


def sample_value(value):
    t = json_type(value)
    if t == "null":
        return colored("null", C["RED"])
    if t == "boolean":
        return colored(str(value).lower(), C["MAGENTA"])
    if t == "number":
        return colored(str(value), C["YELLOW"])
    if t == "string":
        return colored(f'"{ truncate(value)}"', C["GREEN"])
    return None


def print_structure(data, jq_path="", indent=0):
    prefix = "  " * indent
    t = json_type(data)

    if t == "object":
        if not data:
            print(f"{prefix}{colored('{{}}', C['DIM'])}  {colored(jq_display(jq_path), C['DIM'])}")
            return
        for key in data:
            child = data[key]
            child_path = jq_child_path(jq_path, key)
            child_type = json_type(child)
            label = type_label(child)
            sample = sample_value(child)

            line = f"{prefix}{C['BOLD']}{key}{C['RESET']}: {label}"
            if sample is not None:
                line += f"  = {sample}"
            line += f"  {colored(child_path, C['DIM'])}"
            print(line)

            if child_type == "object":
                print_structure(child, child_path, indent + 1)
            elif child_type == "array":
                print_array_structure(child, child_path, indent + 1)

    elif t == "array":
        print_array_structure(data, jq_path, indent)
    else:
        sample = sample_value(data)
        label = type_label(data)
        line = f"{prefix}{label}"
        if sample is not None:
            line += f"  = {sample}"
        line += f"  {colored(jq_display(jq_path), C['DIM'])}"
        print(line)


def object_signature(obj):
    return frozenset(obj.keys())


def group_objects_by_shape(indexed_objects):
    shapes = {}
    for idx, obj in indexed_objects:
        sig = object_signature(obj)
        shapes.setdefault(sig, []).append((idx, obj))
    return shapes


def format_indices(indices):
    if len(indices) <= 5:
        return ", ".join(str(i) for i in indices)
    return ", ".join(str(i) for i in indices[:4]) + f", ...+{len(indices) - 4} more"


def print_array_structure(arr, jq_path, indent):
    prefix = "  " * indent
    if not arr:
        print(f"{prefix}{colored('[] (empty)', C['DIM'])}")
        return

    element_types = {}
    for i, item in enumerate(arr):
        t = json_type(item)
        element_types.setdefault(t, []).append((i, item))

    is_homogeneous = len(element_types) == 1
    single_type = next(iter(element_types)) if is_homogeneous else None

    if is_homogeneous and single_type == "object":
        objects = element_types["object"]
        shapes = group_objects_by_shape(objects)
        if len(shapes) == 1:
            representative = objects[0][1]
            print(f"{prefix}{colored('[each element]', C['DIM'])}")
            print_structure(representative, jq_index_path(jq_path), indent + 1)
            if len(objects) > 1:
                all_keys = set()
                for _, obj in objects:
                    all_keys.update(obj.keys())
                first_keys = set(representative.keys())
                extra = all_keys - first_keys
                if extra:
                    print(
                        f"{prefix}  {colored(f'(other elements also have: {", ".join(sorted(extra))})', C['DIM'])}"
                    )
        else:
            print_object_shapes(shapes, jq_path, indent)
        return

    if is_homogeneous and single_type == "array":
        representative = arr[0]
        print(f"{prefix}{colored('[each element]', C['DIM'])}")
        print_structure(representative, jq_index_path(jq_path), indent + 1)
        return

    if is_homogeneous:
        items = [item for _, item in element_types[single_type]]
        samples = [sample_value(v) for v in items[:MAX_ARRAY_PREVIEW]]
        preview = ", ".join(s for s in samples if s is not None)
        if len(items) > MAX_ARRAY_PREVIEW:
            preview += f", {colored(f'...+{len(items) - MAX_ARRAY_PREVIEW} more', C['DIM'])}"
        print(
            f"{prefix}{colored(f'[{single_type} values]', C['DIM'])}: [{preview}]  {colored(jq_index_path(jq_path), C['DIM'])}"
        )
        return

    print(f"{prefix}{colored('mixed types:', C['DIM'])}")
    for t, indexed_items in element_types.items():
        indices = [i for i, _ in indexed_items]
        label = colored(t, TYPE_COLORS.get(t, C["RESET"]))
        idx_hint = colored(f"  at [{format_indices(indices)}]", C["DIM"])

        if t == "object":
            shapes = group_objects_by_shape(indexed_items)
            print(f"{prefix}  {label} x{len(indexed_items)}{idx_hint}")
            print_object_shapes(shapes, jq_path, indent + 1)
        elif t == "array":
            print(f"{prefix}  {label} x{len(indexed_items)}{idx_hint}")
            representative = indexed_items[0][1]
            print_structure(representative, jq_index_path(jq_path, indexed_items[0][0]), indent + 2)
        else:
            items = [item for _, item in indexed_items]
            samples = [sample_value(v) for v in items[:MAX_ARRAY_PREVIEW]]
            preview = ", ".join(s for s in samples if s is not None)
            if len(items) > MAX_ARRAY_PREVIEW:
                preview += f", {colored(f'...+{len(items) - MAX_ARRAY_PREVIEW} more', C['DIM'])}"
            print(f"{prefix}  {label} x{len(indexed_items)}: [{preview}]{idx_hint}")


def print_object_shapes(shapes, jq_path, indent):
    prefix = "  " * indent
    sorted_shapes = sorted(shapes.items(), key=lambda kv: -len(kv[1][0][1]))

    for i, (sig, indexed_objects) in enumerate(sorted_shapes):
        indices = [idx for idx, _ in indexed_objects]
        representative = max((obj for _, obj in indexed_objects), key=lambda o: len(o))
        key_count = len(representative)
        keys_preview = ", ".join(sorted(sig)[:5])
        if len(sig) > 5:
            keys_preview += ", ..."

        if len(indices) == 1:
            idx = indices[0]
            idx_label = colored(jq_index_path(jq_path, idx), C["DIM"])
            print(f"{prefix}  {colored(f'shape {i+1}', C['CYAN'])} ({key_count} keys: {keys_preview})  x1 {idx_label}")
            print_structure(representative, jq_index_path(jq_path, idx), indent + 2)
        else:
            idx_label = colored(f"at [{format_indices(indices)}]", C["DIM"])
            print(f"{prefix}  {colored(f'shape {i+1}', C['CYAN'])} ({key_count} keys: {keys_preview})  x{len(indices)} {idx_label}")
            print_structure(representative, jq_index_path(jq_path), indent + 2)


def collect_jq_paths(data, jq_path="", paths=None):
    if paths is None:
        paths = []

    t = json_type(data)
    if t == "object":
        for key in data:
            child = data[key]
            child_path = jq_child_path(jq_path, key)
            child_type = json_type(child)
            if child_type in ("string", "number", "boolean", "null"):
                paths.append((child_path, child_type))
            elif child_type == "object":
                collect_jq_paths(child, child_path, paths)
            elif child_type == "array":
                paths.append((jq_index_path(child_path), f"array({len(child)})"))
                if child:
                    collect_array_paths(child, child_path, paths)
    elif t == "array":
        paths.append((jq_index_path(jq_path), f"array({len(data)})"))
        if data:
            collect_array_paths(data, jq_path, paths)
    return paths


def collect_array_paths(arr, jq_path, paths):
    element_types = {}
    for i, item in enumerate(arr):
        t = json_type(item)
        element_types.setdefault(t, []).append((i, item))

    is_homogeneous = len(element_types) == 1

    if is_homogeneous:
        single_type = next(iter(element_types))
        if single_type == "object":
            shapes = group_objects_by_shape(element_types["object"])
            if len(shapes) == 1:
                representative = element_types["object"][0][1]
                collect_jq_paths(representative, jq_index_path(jq_path), paths)
            else:
                sorted_shapes = sorted(shapes.items(), key=lambda kv: -len(kv[1][0][1]))
                for sig, indexed_objects in sorted_shapes:
                    representative = max((obj for _, obj in indexed_objects), key=lambda o: len(o))
                    indices = [idx for idx, _ in indexed_objects]
                    if len(indices) == 1:
                        collect_jq_paths(representative, jq_index_path(jq_path, indices[0]), paths)
                    else:
                        collect_jq_paths(representative, jq_index_path(jq_path), paths)
        elif single_type == "array" and arr:
            collect_array_paths(arr[0], jq_index_path(jq_path), paths)
    else:
        for t, indexed_items in element_types.items():
            if t == "object":
                shapes = group_objects_by_shape(indexed_items)
                sorted_shapes = sorted(shapes.items(), key=lambda kv: -len(kv[1][0][1]))
                for sig, indexed_objects in sorted_shapes:
                    representative = max((obj for _, obj in indexed_objects), key=lambda o: len(o))
                    indices = [idx for idx, _ in indexed_objects]
                    if len(indices) == 1:
                        collect_jq_paths(representative, jq_index_path(jq_path, indices[0]), paths)
                    else:
                        collect_jq_paths(representative, jq_index_path(jq_path), paths)
            elif t == "array":
                collect_array_paths(indexed_items[0][1], jq_index_path(jq_path, indexed_items[0][0]), paths)


def load_json(source):
    if source == "-":
        if sys.stdin.isatty():
            print("Error: no input (provide a file or pipe JSON to stdin)", file=sys.stderr)
            sys.exit(1)
        raw = sys.stdin.read()
    else:
        path = Path(source)
        if not path.exists():
            print(f"Error: file not found: {source}", file=sys.stderr)
            sys.exit(1)
        raw = path.read_text()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)


def build_argument_parser():
    parser = argparse.ArgumentParser(
        prog="jsonmin",
        description="Reveal the structure of any JSON file at a glance.",
        epilog="Examples:\n"
               "  jsonmin.py response.json\n"
               "  jsonmin.py response.json --paths\n"
               "  curl -s https://api.example.com/data | jsonmin.py\n"
               "  cat response.json | jsonmin.py --paths\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "file",
        nargs="?",
        default="-",
        help="JSON file to analyze (default: read from stdin)",
    )
    parser.add_argument(
        "--paths",
        action="store_true",
        help="show flat list of all jq-compatible paths instead of tree",
    )
    return parser


def main():
    parser = build_argument_parser()
    args = parser.parse_args()

    data = load_json(args.file)

    root_label = type_label(data)
    print(f"\n{C['BOLD']}Root:{C['RESET']} {root_label}\n")

    if args.paths:
        paths = collect_jq_paths(data)
        max_path_len = max((len(p) for p, _ in paths), default=0)
        for path, ptype in paths:
            color = TYPE_COLORS.get(ptype, C["DIM"])
            print(f"  {C['BOLD']}{path:<{max_path_len}}{C['RESET']}  {colored(ptype, color)}")
        print()
        print(f"{C['DIM']}Use with jq:  cat file.json | jq '<path>'{C['RESET']}")
        print()
    else:
        print_structure(data, "", 0)
        print()


if __name__ == "__main__":
    main()
