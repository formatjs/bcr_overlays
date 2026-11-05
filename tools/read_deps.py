#!/usr/bin/env python3
"""Read Chromium's declarative DEPS without executing Python or evaluating conditions."""

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re


def parse_deps(source: str) -> dict:
    assignments = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)):
            raise ValueError(f"nondeclarative DEPS statement at line {node.lineno}")
        name = node.targets[0].id
        if name in assignments:
            raise ValueError(f"repeated DEPS assignment: {name}")
        assignments[name] = node.value

    variables = assignments["vars"]
    if not isinstance(variables, ast.Dict):
        raise ValueError("DEPS vars must be a literal dictionary")
    variable_nodes = {ast.literal_eval(key): value for key, value in zip(variables.keys, variables.values)}
    resolved = {}
    resolving = set()

    def variable(name):
        if name not in variable_nodes:
            raise ValueError(f"unknown Var: {name}")
        if name in resolving:
            raise ValueError(f"cyclic Var: {name}")
        if name not in resolved:
            resolving.add(name)
            resolved[name] = value(variable_nodes[name])
            resolving.remove(name)
        return resolved[name]

    def value(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.List):
            return [value(item) for item in node.elts]
        if isinstance(node, ast.Dict) and all(key is not None for key in node.keys):
            return {value(key): value(item) for key, item in zip(node.keys, node.values)}
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return value(node.left) + value(node.right)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and len(node.args) == 1 and not node.keywords:
            if node.func.id == "Var":
                return variable(value(node.args[0]))
            if node.func.id == "Str":
                result = value(node.args[0])
                if isinstance(result, str):
                    return result
        raise ValueError(f"unsupported DEPS expression at line {node.lineno}")

    def expand_url(url):
        seen = set()
        pattern = re.compile(r"\{([A-Za-z_][A-Za-z_0-9]*)\}")
        while pattern.search(url):
            if url in seen:
                raise ValueError("cyclic DEPS URL template")
            seen.add(url)
            url = pattern.sub(lambda match: str(variable(match[1])), url)
        if "{" in url or "}" in url:
            raise ValueError(f"unsupported DEPS URL template: {url}")
        return url

    dependencies = value(assignments["deps"])
    for name, spec in dependencies.items():
        if isinstance(spec, str):
            dependencies[name] = expand_url(spec)
        elif isinstance(spec, dict) and isinstance(spec.get("url"), str):
            spec["url"] = expand_url(spec["url"])

    return {
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "variables": {name: variable(name) for name in variable_nodes},
        "deps": dependencies,
        "gclient_gn_args": {
            name: variable(name)
            for name in value(assignments.get("gclient_gn_args", ast.List(elts=[])))
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = json.dumps(parse_deps(args.source.read_text()), indent=2) + "\n"
    if args.output:
        args.output.write_text(result)
    else:
        print(result, end="")


if __name__ == "__main__":
    main()
