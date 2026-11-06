"""Shared declared source inputs for native Mojo actions."""

load(":python_action.bzl", "chromium_filegroup")

load(":mojo_parameters.bzl", "input_files")

# buildifier: disable=unnamed-macro
def declare_common_inputs():
    """Declare fixed source groups from captured browser graph."""
    chromium_filegroup(
        name = "inputs_mojo_755211961de3c039",
        srcs = input_files([550]),
    )
    chromium_filegroup(
        name = "inputs_mojo_f55f48e469584939",
        srcs = input_files([551, 12012, 12048, 12064, 12067]),
    )
    chromium_filegroup(
        name = "inputs_mojo_61ea34c4bdb4e0b0",
        srcs = input_files([0, 1, 2, 544, 545, 546, 547, 548, 549, 552, 553, 605, 643, 644, 645, 646, 647, 648, 661, 664, 665, 666, 667, 668, 669, 670, 671, 672, 673, 674, 675, 676, 677, 678, 32898, 32899, 32900, 32901, 32902, 32903, 32904, 32905, 32906, 32907, 32908, 32909, 32910, 32911, 32912, 32913, 32914, 32915, 32916, 32917, 32918, 32919, 32920, 32921, 32922, 32923, 32924, 32925, 32926]),
    )
    chromium_filegroup(
        name = "inputs_mojo_b933dce347a82ef6",
        srcs = input_files([660, 12063, 32929, 32930, 32931]),
    )
    chromium_filegroup(
        name = "inputs_mojo_30eb467f2d848509",
        srcs = input_files([0, 1, 2, 544, 545, 546, 547, 548, 549, 553, 605, 643, 644, 645, 646, 647, 648, 661, 664, 665, 666, 667, 668, 669, 670, 671, 672, 673, 674, 675, 676, 677, 678, 32898, 32899, 32900, 32901, 32902, 32903, 32904, 32905, 32906, 32907, 32908, 32909, 32910, 32911, 32912, 32913, 32914, 32915, 32916, 32917, 32918, 32919, 32920, 32921, 32922, 32923, 32924, 32925, 32926]),
    )
    chromium_filegroup(
        name = "inputs_mojo_649652cc91b80f77",
        srcs = input_files([662]),
    )
    chromium_filegroup(
        name = "inputs_mojo_1ea987b5f889840f",
        srcs = input_files([663]),
    )
    chromium_filegroup(
        name = "inputs_mojo_f3a66324fe520d42",
        srcs = input_files([664, 665, 666, 667, 668, 669, 670, 671, 672, 673, 674, 675, 676, 677, 678, 679, 32933, 32934, 32935]),
    )
    chromium_filegroup(
        name = "inputs_mojo_b1c34e6bcf9aa864",
        srcs = input_files([32881, 32882, 32883, 32884, 32885, 32888, 32889, 32890, 32891, 32892, 32893, 32896, 32897, 32898, 32899, 32900, 32901, 32902, 32903, 32904, 32905, 32906, 32907, 32908, 32909, 32910, 32911, 32912, 32913, 32914, 32915, 32916, 32917, 32918, 32919, 32920, 32921, 32922, 32923, 32924, 32925, 32926, 32936, 32937, 32938, 32939]),
    )
    chromium_filegroup(
        name = "inputs_mojo_94828aabbcb99be6",
        srcs = input_files([32927, 32928, 32929, 32930, 32931, 32932]),
    )
