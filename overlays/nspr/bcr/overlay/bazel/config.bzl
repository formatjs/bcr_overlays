"""Deterministic Linux configuration artifacts."""

def _configuration_impl(ctx):
    cpu = ctx.actions.declare_file("prcpucfg.h")
    ctx.actions.symlink(output = cpu, target_file = ctx.file.cpu)
    outputs = [cpu]
    for name in ["_pr_bld.h", "_pl_bld.h"]:
        header = ctx.actions.declare_file(name)
        production = '#define _PRODUCTION "libnspr4.a"\n' if name == "_pr_bld.h" else """#ifdef NSPR_PLDS_BUILD
#define _PRODUCTION "libplds4.a"
#else
#define _PRODUCTION "libplc4.a"
#endif
"""
        ctx.actions.write(header, '#define _BUILD_TIME 0LL\n#define _BUILD_STRING ""\n' + production)
        outputs.append(header)
    return [DefaultInfo(files = depset(outputs))]

linux_configuration = rule(
    implementation = _configuration_impl,
    attrs = {"cpu": attr.label(allow_single_file = True, mandatory = True)},
)
