"""Shared declared source inputs for native Mojo actions."""

load(":mojo_parameters.bzl", "input_files")
load(":python_action.bzl", "chromium_filegroup")

# buildifier: disable=unnamed-macro
def declare_common_inputs():
    """Declare fixed source groups from captured browser graph."""
    chromium_filegroup(
        name = "inputs_mojo_755211961de3c039",
        srcs = input_files([539]),
    )
    chromium_filegroup(
        name = "inputs_mojo_f55f48e469584939",
        srcs = input_files([540, 11884, 11920, 11936, 11939]),
    )
    chromium_filegroup(
        name = "inputs_mojo_61ea34c4bdb4e0b0",
        srcs = input_files([0, 1, 2, 533, 534, 535, 536, 537, 538, 541, 542, 594, 632, 633, 634, 635, 636, 637, 650, 653, 654, 655, 656, 657, 658, 659, 660, 661, 662, 663, 664, 665, 666, 667, 32729, 32730, 32731, 32732, 32733, 32734, 32735, 32736, 32737, 32738, 32739, 32740, 32741, 32742, 32743, 32744, 32745, 32746, 32747, 32748, 32749, 32750, 32751, 32752, 32753, 32754, 32755, 32756, 32757]),
    )
    chromium_filegroup(
        name = "inputs_mojo_b933dce347a82ef6",
        srcs = input_files([649, 11935, 32760, 32761, 32762, 32763]),
    )
    chromium_filegroup(
        name = "inputs_mojo_30eb467f2d848509",
        srcs = input_files([0, 1, 2, 533, 534, 535, 536, 537, 538, 542, 594, 632, 633, 634, 635, 636, 637, 650, 653, 654, 655, 656, 657, 658, 659, 660, 661, 662, 663, 664, 665, 666, 667, 32729, 32730, 32731, 32732, 32733, 32734, 32735, 32736, 32737, 32738, 32739, 32740, 32741, 32742, 32743, 32744, 32745, 32746, 32747, 32748, 32749, 32750, 32751, 32752, 32753, 32754, 32755, 32756, 32757]),
    )
    chromium_filegroup(
        name = "inputs_mojo_649652cc91b80f77",
        srcs = input_files([651]),
    )
    chromium_filegroup(
        name = "inputs_mojo_1ea987b5f889840f",
        srcs = input_files([652]),
    )
    chromium_filegroup(
        name = "inputs_mojo_f3a66324fe520d42",
        srcs = input_files([653, 654, 655, 656, 657, 658, 659, 660, 661, 662, 663, 664, 665, 666, 667, 668, 32765, 32766, 32767]),
    )
    chromium_filegroup(
        name = "inputs_mojo_b1c34e6bcf9aa864",
        srcs = input_files([32712, 32713, 32714, 32715, 32716, 32719, 32720, 32721, 32722, 32723, 32724, 32727, 32728, 32729, 32730, 32731, 32732, 32733, 32734, 32735, 32736, 32737, 32738, 32739, 32740, 32741, 32742, 32743, 32744, 32745, 32746, 32747, 32748, 32749, 32750, 32751, 32752, 32753, 32754, 32755, 32756, 32757, 32768, 32769, 32770, 32771]),
    )
    chromium_filegroup(
        name = "inputs_mojo_94828aabbcb99be6",
        srcs = input_files([32758, 32759, 32760, 32761, 32762, 32763, 32764]),
    )
