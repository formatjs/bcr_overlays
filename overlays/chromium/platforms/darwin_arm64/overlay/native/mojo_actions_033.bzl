"""Generated Mojo action shard; run tools/import_mojo_actions.py."""

load(":python_action.bzl", "chromium_filegroup", "chromium_python_action")

load(":mojo_parameters.bzl", "arguments", "input_files", "output_files", "source_path")

# buildifier: disable=unnamed-macro
def declare_actions():
    """Declare fixed targets from captured browser graph."""
    chromium_python_action(
        name = "mojo_44894f37191c8a0a",
        srcs = input_files([14884, 33963, 34032, 34047, 34880]),
        outs = output_files([33957, 33958, 33964, 33965, 33966, 33968, 33969]),
        script = source_path(662),
        args = arguments([1755, 1760, 3558, 7050, 1758, 1762, 1757, 1762, 1, 5672, 1324, 1328, 1759, 3274]),
        response_file_contents = arguments([]),
        deps = [":mojo_0636a12c9995226c", ":mojo_4e3d0d0143ba8901", ":inputs_mojo_30eb467f2d848509"],
    )
    chromium_python_action(
        name = "mojo_efaf1a4315b8f5a8",
        srcs = input_files([1456, 2440, 2489, 2498, 34880]),
        outs = output_files([2436, 2437, 2441, 2442, 2443, 2445, 2446]),
        script = source_path(662),
        args = arguments([1755, 1760, 3275, 7050, 1758, 1762, 1757, 1762, 1, 3339, 54, 1328, 1759, 3274]),
        response_file_contents = arguments([]),
        deps = [":mojo_2178b496c1db85af", ":mojo_094406c16b1a2b09", ":inputs_mojo_30eb467f2d848509"],
    )
