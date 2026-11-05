"""Original inspector-overlay TypeScript, Rollup and resource copies."""

load("//native/rust:tools.bzl", "import_executable")
load(":devtools_inspector_sources.bzl", "ACTIONS", "COPIES", "GROUPS", "SUPPORT")
load(":node_inputs.bzl", "DEVTOOLS_BUILD_PACKAGES", "DEVTOOLS_I18N_PACKAGES", "chromium_npm_inputs")
load(":python_action.bzl", "chromium_filegroup", "chromium_python_action")
load(":resource_copy.bzl", "chromium_resource_copy")
load(":tool_inputs.bzl", "chromium_tool_inputs")

def native_devtools_inspector():
    chromium_npm_inputs(
        name = "devtools_inspector_npm",
        packages = DEVTOOLS_BUILD_PACKAGES,
        src = "@chromium_devtools_frontend//:npm_files",
        manifest = "@chromium_devtools_frontend//:node_modules/typescript/package.json",
        logical_root = "third_party/devtools-frontend/src/node_modules",
    )
    chromium_npm_inputs(
        name = "devtools_i18n_npm",
        src = "@chromium_devtools_frontend//:npm_files",
        manifest = "@chromium_devtools_frontend//:node_modules/typescript/package.json",
        logical_root = "third_party/devtools-frontend/src/node_modules",
        packages = DEVTOOLS_I18N_PACKAGES,
    )
    import_executable(name = "devtools_inspector_esbuild", src = "@chromium_devtools_esbuild//:esbuild")
    chromium_tool_inputs(
        name = "devtools_inspector_esbuild_inputs",
        tool = ":devtools_inspector_esbuild",
        logical_path = "third_party/devtools-frontend/src/third_party/esbuild/esbuild",
    )
    chromium_filegroup(name = "devtools_inspector_runtime", srcs = SUPPORT)
    for copy in COPIES:
        chromium_resource_copy(**copy)
    for action in ACTIONS:
        chromium_python_action(propagate_inputs = action["script"].endswith("/ts_library.py"), **action)
    for group in GROUPS:
        chromium_filegroup(**group)
    native.filegroup(
        name = "devtools_inspector_assets",
        srcs = [":" + record["name"] for record in COPIES + ACTIONS],
    )
