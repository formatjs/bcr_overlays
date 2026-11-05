"""Native Linux NSS libraries from the resolved upstream graph."""

load("@rules_cc//cc:cc_binary.bzl", "cc_binary")
load("@rules_cc//cc:cc_import.bzl", "cc_import")
load("@rules_cc//cc:cc_library.bzl", "cc_library")
load(":actions.bzl", "generate")
load(":sources.bzl", "TARGETS")

def native_nss():
    for name, target in TARGETS.items():
        if name == "nss_sign_shared_libs":
            continue
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
        srcs = target["sources"]
        common = {
            "srcs": srcs,
            "copts": target["copts"],
            "conlyopts": target["conlyopts"],
            "cxxopts": target["cxxopts"],
            "local_defines": target["defines"],
            "includes": target["includes"],
            "deps": deps,
            "linkstatic": True,
        }
        if target["type"] == "shared_library":
            linkopts = target["linkopts"] + ["-ldl", "-pthread", "-Wl,-soname,lib" + name + ".so"]
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
                linkopts.append("-Wl,--version-script,$(location :" + output + ")")
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
                linkopts = target["linkopts"],
                data = [":nss_libs"] if name == "shlibsign" else [":nss_libs", ":module_checksums"],
                **common
            )
        else:
            cc_library(name = name, alwayslink = bool(srcs), **common)
