"""Compare the complete upstream binding output set with bounded parallelism."""

load("@chromium//native:python_action.bzl", "chromium_python_action")

def _source(value):
    if value.startswith(":"):
        return Label("@chromium_darwin_arm64//native" + value)
    if value.startswith("//"):
        return Label("@chromium_darwin_arm64" + value)
    return Label(value)

def bindings_candidate(name, actions):
    action = [entry for entry in actions if entry["name"] == "blink_core_d891bf49f6c231ad_0"][0]
    chromium_python_action(
        name = name,
        srcs = {_source(label): logical for label, logical in action["srcs"].items()},
        outs = {"candidate/" + path: logical for path, logical in action["outs"].items()},
        script = action["script"],
        args = ["--single_process"] + action["args"],
        response_file_contents = action["response_file_contents"],
        tags = ["manual"],
    )

def _by_name(target):
    result = {}
    for file in target[DefaultInfo].files.to_list():
        marker = "gen/third_party/blink/"
        parts = file.path.split(marker)
        if len(parts) != 2:
            fail("unexpected binding output: " + file.path)
        name = marker + parts[1]
        if name in result:
            fail("duplicate binding output: " + name)
        result[name] = file
    return result

def _compare(ctx):
    baseline, candidate = _by_name(ctx.attr.baseline), _by_name(ctx.attr.candidate)
    if sorted(baseline) != sorted(candidate) or not baseline:
        fail("binding output sets differ")
    manifest = ctx.actions.declare_file(ctx.label.name + ".inputs.json")
    ctx.actions.write(manifest, json.encode([
        {"name": name, "baseline": baseline[name].path, "candidate": candidate[name].path}
        for name in sorted(baseline)
    ]))
    report = ctx.actions.declare_file(ctx.label.name + ".report.json")
    runtime = ctx.attr._python[platform_common.ToolchainInfo].py3_runtime
    ctx.actions.run(
        executable = runtime.interpreter,
        arguments = ["-I", "-B", ctx.file._script.path, manifest.path, report.path],
        inputs = depset(baseline.values() + candidate.values() + [manifest, ctx.file._script], transitive = [runtime.files]),
        outputs = [report],
        mnemonic = "BindingsCompare",
    )
    return [DefaultInfo(files = depset([report]))]

compare_bindings = rule(
    implementation = _compare,
    attrs = {
        "baseline": attr.label(mandatory = True),
        "candidate": attr.label(mandatory = True),
        "_script": attr.label(default = Label(":compare.py"), allow_single_file = True),
        "_python": attr.label(default = Label("@rules_python//python:current_py_toolchain"), cfg = "exec"),
    },
)
