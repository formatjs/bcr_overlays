"""Native Linux NSS libraries from the resolved upstream graph."""

load("@rules_cc//cc:cc_binary.bzl", "cc_binary")
load("@rules_cc//cc:cc_import.bzl", "cc_import")
load("@rules_cc//cc:cc_library.bzl", "cc_library")
load(":actions.bzl", "generate")
load(":sources.bzl", "TARGETS")
load(":sources_arm64.bzl", ARM64_TARGETS = "TARGETS")

def _architecture(amd64, arm64):
    return amd64 if amd64 == arm64 else select({
        "@platforms//cpu:aarch64": arm64,
        "//conditions:default": amd64,
    })

def _dependencies(name, target):
    deps = [
        ":" + dep + ("_link" if TARGETS[dep]["type"] == "shared_library" else "")
        for dep in target["deps"]
        if dep != "nss_sign_shared_libs"
    ]
    deps += [":headers", "@nspr//:shared"]
    for library in target["libraries"]:
        if library == "-lsqlite3":
            deps.append("@sqlite3")
        elif library == "-lz":
            deps.append("@zlib")
        elif library not in ["-lc", "-ldl", "-lpthread", "-lnspr4", "-lplc4", "-lplds4"]:
            fail("unmapped NSS library: " + library)
    if name == "sqlite3":
        deps.append("@sqlite3")
    return deps

def native_nss():
    for name, target in TARGETS.items():
        if name == "nss_sign_shared_libs":
            continue
        arm64 = ARM64_TARGETS[name]
        if target["type"] != arm64["type"] or target["mapfile"] != arm64["mapfile"]:
            fail("NSS target layout differs between architectures: " + name)
        deps = _architecture(_dependencies(name, target), _dependencies(name, arm64))
        common = {
            "srcs": _architecture(target["sources"], arm64["sources"]),
            "copts": _architecture(target["copts"], arm64["copts"]),
            "conlyopts": _architecture(target["conlyopts"], arm64["conlyopts"]),
            "cxxopts": _architecture(target["cxxopts"], arm64["cxxopts"]),
            "local_defines": _architecture(target["defines"], arm64["defines"]),
            "includes": _architecture(target["includes"], arm64["includes"]),
            "deps": deps,
            "linkstatic": True,
        }
        if target["type"] == "shared_library":
            linkopts = _architecture(target["linkopts"], arm64["linkopts"]) + ["-ldl", "-pthread", "-Wl,-soname,lib" + name + ".so"]
            inputs = []
            if target["mapfile"]:
                output = "generated/" + name + ".def"
                generate(
                    name = name + "_mapfile",
                    tool = "//bazel:mapfile_generator",
                    source = target["mapfile"],
                    out = output,
                )
                inputs.append(":" + output)
                linkopts = linkopts + ["-Wl,--version-script,$(location :" + output + ")"]
            cc_binary(
                name = "lib" + name + ".so",
                linkshared = True,
                linkopts = linkopts,
                additional_linker_inputs = inputs,
                **common
            )
            cc_import(
                name = name + "_link",
                shared_library = ":lib" + name + ".so",
                deps = [":headers", "@nspr//:shared"],
            )
            cc_library(
                name = name,
                data = [":nss_libs", ":module_checksums"],
                deps = [":" + name + "_link"],
            )
        elif target["type"] == "executable":
            cc_binary(
                name = name,
                linkopts = _architecture(target["linkopts"], arm64["linkopts"]),
                data = [":nss_libs"] if name == "shlibsign" else [":nss_libs", ":module_checksums"],
                **common
            )
        else:
            cc_library(name = name, alwayslink = bool(target["sources"]) or bool(arm64["sources"]), **common)
