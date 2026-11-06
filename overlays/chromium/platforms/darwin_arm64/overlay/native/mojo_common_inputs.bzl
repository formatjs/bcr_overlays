"""Shared declared source inputs for native Mojo actions."""

load(":mojo_parameters.bzl", "input_files")
load(":python_action.bzl", "chromium_filegroup")

# buildifier: disable=unnamed-macro
def declare_common_inputs():
    """Declare fixed source groups from captured browser graph."""
    chromium_filegroup(
        name = "inputs_mojo_755211961de3c039",
        srcs = input_files([551]),
    )
    chromium_filegroup(
        name = "inputs_mojo_f55f48e469584939",
        srcs = input_files([552, 13846, 13882, 13898, 13901]),
    )
    chromium_filegroup(
        name = "inputs_mojo_61ea34c4bdb4e0b0",
        srcs = input_files([0, 1, 2, 545, 546, 547, 548, 549, 550, 553, 554, 606, 644, 645, 646, 647, 648, 649, 662, 665, 666, 667, 668, 669, 670, 671, 672, 673, 674, 675, 676, 677, 678, 679, 34740, 34741, 34742, 34743, 34744, 34745, 34746, 34747, 34748, 34749, 34750, 34751, 34752, 34753, 34754, 34755, 34756, 34757, 34758, 34759, 34760, 34761, 34762, 34763, 34764, 34765, 34766, 34767, 34768]),
    )
    chromium_filegroup(
        name = "inputs_mojo_b933dce347a82ef6",
        srcs = input_files([661, 34771, 34772, 34773, 34774]),
    )
    chromium_filegroup(
        name = "inputs_mojo_30eb467f2d848509",
        srcs = input_files([0, 1, 2, 545, 546, 547, 548, 549, 550, 554, 606, 644, 645, 646, 647, 648, 649, 662, 665, 666, 667, 668, 669, 670, 671, 672, 673, 674, 675, 676, 677, 678, 679, 34740, 34741, 34742, 34743, 34744, 34745, 34746, 34747, 34748, 34749, 34750, 34751, 34752, 34753, 34754, 34755, 34756, 34757, 34758, 34759, 34760, 34761, 34762, 34763, 34764, 34765, 34766, 34767, 34768]),
    )
    chromium_filegroup(
        name = "inputs_mojo_649652cc91b80f77",
        srcs = input_files([663]),
    )
    chromium_filegroup(
        name = "inputs_mojo_1ea987b5f889840f",
        srcs = input_files([664]),
    )
    chromium_filegroup(
        name = "inputs_mojo_f3a66324fe520d42",
        srcs = input_files([665, 666, 667, 668, 669, 670, 671, 672, 673, 674, 675, 676, 677, 678, 679, 680, 34776, 34777, 34778]),
    )
    chromium_filegroup(
        name = "inputs_mojo_b1c34e6bcf9aa864",
        srcs = input_files([34723, 34724, 34725, 34726, 34727, 34730, 34731, 34732, 34733, 34734, 34735, 34738, 34739, 34740, 34741, 34742, 34743, 34744, 34745, 34746, 34747, 34748, 34749, 34750, 34751, 34752, 34753, 34754, 34755, 34756, 34757, 34758, 34759, 34760, 34761, 34762, 34763, 34764, 34765, 34766, 34767, 34768, 34779, 34780, 34781, 34782]),
    )
    chromium_filegroup(
        name = "inputs_mojo_94828aabbcb99be6",
        srcs = input_files([34769, 34770, 34771, 34772, 34773, 34774, 34775]),
    )
