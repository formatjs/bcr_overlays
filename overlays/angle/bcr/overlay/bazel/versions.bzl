"""Native version-header actions for pinned archive builds."""

def _file_path(file):
    return file.path

def _versions_impl(ctx):
    commit = ctx.actions.declare_file(ctx.label.name + "/angle_commit.h")
    program = ctx.actions.declare_file(ctx.label.name + "/ANGLEShaderProgramVersion.h")
    response = ctx.actions.declare_file(ctx.label.name + ".rsp")
    sources = sorted(depset(ctx.files.srcs).to_list(), key = _file_path)
    ctx.actions.write(response, "\n".join([file.path for file in sources]))
    ctx.actions.write(
        commit,
        "\n".join([
            '#define ANGLE_COMMIT_HASH "{}"'.format(ctx.attr.commit_hash),
            "#define ANGLE_COMMIT_HASH_SIZE {}".format(len(ctx.attr.commit_hash)),
            '#define ANGLE_COMMIT_DATE "unknown date"',
            "#define ANGLE_COMMIT_POSITION 0",
            "",
        ]),
    )
    ctx.actions.run(
        executable = ctx.attr._program_tool[DefaultInfo].files_to_run,
        arguments = [program.path, response.path],
        inputs = sources + [response],
        outputs = [program],
        mnemonic = "AngleProgramVersion",
    )
    return [DefaultInfo(files = depset([commit, program]))]

angle_versions = rule(
    implementation = _versions_impl,
    attrs = {
        "commit_hash": attr.string(mandatory = True),
        "srcs": attr.label_list(allow_files = True, mandatory = True),
        "_program_tool": attr.label(
            default = Label("//:program_version_tool"),
            executable = True,
            cfg = "exec",
        ),
    },
)
