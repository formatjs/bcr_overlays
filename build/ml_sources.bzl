"""Pinned TFLite and XNNPACK inputs for Chromium's captured ML profile."""

load("@bazel_tools//tools/build_defs/repo:http.bzl", "http_archive")

def chromium_ml_sources(ctx):
    for name, project, revision, sha256 in [
        ("tflite", "tensorflow/tensorflow", "313f58ae85278ced9ccc7f90ee630bdf8735c52f", "e3e58c5c5133090be116d110f4461d9675e1bc30e1afc037cbf2bf6c3aa34ae9"),
        ("xnnpack", "google/XNNPACK", "4d098efeac50c44a7c03e6feb1794908db4c3158", "6f9e694124d7c309c3b7937eeac4855cb2e0062a1ae017f9938203e200ce2a95"),
        ("ruy", "google/ruy", "9940fbf1e0c0863907e77e0600b99bb3e2bc2b9f", "36683d593c7e8ddd9f001b13f5675235a8a31437100c35f18c9f3cd85395717c"),
        ("eigen3", "eigen-mirror/eigen", "430e35fbd15d3c946d2d2ba19ec41c16ba217cb3", "0facaf8f690877b310ed20cc713fec2b68e9e17261b5a072c7627714a9b32470"),
        ("gemmlowp", "google/gemmlowp", "16e8662c34917be0065110bfcd9cc27d30f52fdf", "c3feb896a1b42595cf9a508ed64ed0dc3cd84fffdb8eed790d02d0534ab322ce"),
        ("farmhash", "google/farmhash", "816a4ae622e964763ca0862d9dbd19324a1eaf45", "6560547c63e4af82b0f202cb710ceabb3f21347a4b996db565a411da5b17aba0"),
        ("neon_2_sse", "intel/ARM_NEON_2_x86_SSE", "eb8b80b28f956275e291ea04a7beb5ed8289e872", "00824244248d2067334dd46fe8c6cde2c4cebaad5534611007e30d4f35ded7d0"),
    ]:
        http_archive(
            name = "chromium_" + name,
            urls = ["https://codeload.github.com/" + project + "/tar.gz/" + revision],
            type = "tar.gz",
            sha256 = sha256,
            strip_prefix = project.split("/")[1] + "-" + revision,
            # Captured Chromium targets own package boundaries and compilation.
            patch_cmds = ["find . -mindepth 2 -type f \\( -name BUILD -o -name BUILD.bazel \\) -delete"],
            build_file_content = ctx.read(Label("//build:ml_sources.BUILD.bazel")).replace("@@PROJECT@@", name),
        )
