"""Assemble declared Chromium and platform runtime files."""

load(":python_action.bzl", "ChromiumFilesInfo")

def _runtime_bundle_impl(ctx):
    files = {}
    for target, logical in ctx.attr.srcs.items():
        sources = target[DefaultInfo].files.to_list()
        if len(sources) != 1:
            fail("runtime source must identify one file: %s" % target.label)
        if logical in files and files[logical] != sources[0]:
            fail("conflicting runtime path: " + logical)
        files[logical] = sources[0]
    for dependency in ctx.attr.deps:
        for source, path in dependency[ChromiumFilesInfo].mappings.to_list():
            prefix = "out/bazel-import/"
            if not path.startswith(prefix):
                fail("runtime dependency lacks a build-relative path: " + path)
            logical = path[len(prefix):]
            if logical in files and files[logical] != source:
                fail("conflicting runtime path: " + logical)
            files[logical] = source
    output = ctx.actions.declare_directory(ctx.attr.directory or ctx.label.name)
    manifest = ctx.actions.declare_file(ctx.label.name + ".runtime.json")
    ctx.actions.write(manifest, json.encode({
        "inputs": [[files[path].path, path] for path in sorted(files)],
        "output": output.path,
        "symlinks": ctx.attr.symlinks,
    }))
    ctx.actions.run(
        executable = ctx.attr._python[platform_common.ToolchainInfo].py3_runtime.interpreter,
        arguments = ["-I", "-B", ctx.file._script.path, manifest.path],
        inputs = depset([manifest, ctx.file._script] + files.values(), transitive = [ctx.attr._python[platform_common.ToolchainInfo].py3_runtime.files] + [target[DefaultInfo].files for target in ctx.attr.validations]),
        outputs = [output],
        mnemonic = "ChromiumRuntimeBundle",
        progress_message = "Assembling %s" % ctx.label,
    )
    return [DefaultInfo(files = depset([output]))]

chromium_runtime_bundle = rule(
    implementation = _runtime_bundle_impl,
    attrs = {
        "srcs": attr.label_keyed_string_dict(allow_files = True),
        "directory": attr.string(),
        "symlinks": attr.string_dict(),
        "validations": attr.label_list(allow_files = True),
        "deps": attr.label_list(providers = [ChromiumFilesInfo]),
        "_script": attr.label(default = Label("//native:assemble_runtime.py"), allow_single_file = True),
        "_python": attr.label(default = Label("@rules_python//python:current_py_toolchain"), cfg = "exec"),
    },
)
