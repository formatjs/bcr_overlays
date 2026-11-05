"""Shared declared source inputs for native Mojo actions."""

load(":mojo_parameters.bzl", "input_files")
load(":python_action.bzl", "chromium_filegroup")

# buildifier: disable=unnamed-macro
def declare_common_inputs():
    """Declare fixed source groups from captured browser graph."""
    chromium_filegroup(
        name = "inputs_mojo_755211961de3c039",
        srcs = input_files([536]),
    )
    chromium_filegroup(
        name = "inputs_mojo_f55f48e469584939",
        srcs = input_files([537, 31777, 31813, 31829, 31832]),
    )
    chromium_filegroup(
        name = "inputs_mojo_61ea34c4bdb4e0b0",
        srcs = input_files([0, 1, 2, 530, 531, 532, 533, 534, 535, 538, 539, 591, 629, 630, 631, 632, 633, 634, 647, 650, 651, 652, 653, 654, 655, 656, 657, 658, 659, 660, 661, 662, 663, 664, 52622, 52623, 52624, 52625, 52626, 52627, 52628, 52629, 52630, 52631, 52632, 52633, 52634, 52635, 52636, 52637, 52638, 52639, 52640, 52641, 52642, 52643, 52644, 52645, 52646, 52647, 52648, 52649, 52650]),
    )
    chromium_filegroup(
        name = "inputs_mojo_b933dce347a82ef6",
        srcs = input_files([646, 52653, 52654, 52655, 52656]),
    )
    chromium_filegroup(
        name = "inputs_mojo_30eb467f2d848509",
        srcs = input_files([0, 1, 2, 530, 531, 532, 533, 534, 535, 539, 591, 629, 630, 631, 632, 633, 634, 647, 650, 651, 652, 653, 654, 655, 656, 657, 658, 659, 660, 661, 662, 663, 664, 52622, 52623, 52624, 52625, 52626, 52627, 52628, 52629, 52630, 52631, 52632, 52633, 52634, 52635, 52636, 52637, 52638, 52639, 52640, 52641, 52642, 52643, 52644, 52645, 52646, 52647, 52648, 52649, 52650]),
    )
    chromium_filegroup(
        name = "inputs_mojo_649652cc91b80f77",
        srcs = input_files([648]),
    )
    chromium_filegroup(
        name = "inputs_mojo_1ea987b5f889840f",
        srcs = input_files([649]),
    )
    chromium_filegroup(
        name = "inputs_mojo_f3a66324fe520d42",
        srcs = input_files([650, 651, 652, 653, 654, 655, 656, 657, 658, 659, 660, 661, 662, 663, 664, 665, 52658, 52659, 52660]),
    )
    chromium_filegroup(
        name = "inputs_mojo_b1c34e6bcf9aa864",
        srcs = input_files([52605, 52606, 52607, 52608, 52609, 52612, 52613, 52614, 52615, 52616, 52617, 52620, 52621, 52622, 52623, 52624, 52625, 52626, 52627, 52628, 52629, 52630, 52631, 52632, 52633, 52634, 52635, 52636, 52637, 52638, 52639, 52640, 52641, 52642, 52643, 52644, 52645, 52646, 52647, 52648, 52649, 52650, 52661, 52662, 52663, 52664]),
    )
    chromium_filegroup(
        name = "inputs_mojo_94828aabbcb99be6",
        srcs = input_files([52651, 52652, 52653, 52654, 52655, 52656, 52657]),
    )
