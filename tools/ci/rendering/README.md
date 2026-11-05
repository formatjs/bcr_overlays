# Rendering smoke

Two local HTTP fixtures exercise Grid, Flexbox, gradients, transforms, rounded
corners, clipping, an external SVG image, SVG paths and Canvas 2D compositing.
DevTools sets an 800×600 viewport at scale factor 1. The test waits for images,
fonts, fixture readiness and two animation frames before capturing each PNG.
Rendering uses the downloaded Chromium artifact with software rendering and sRGB.

Each screenshot's 720×360 scene is compared with a checked-in PNG. A pixel counts
as changed when any RGB channel differs by more than 24; more than 0.5% changed
pixels fails the case. Exact DOM bounds and Canvas pixel readback are checked
independently. Header/footer text stays outside the compared scene because
system font rasterization varies across operating systems. Full screenshots
retain that text for review.

```sh
python3 -m venv /tmp/chromium-rendering-tools
/tmp/chromium-rendering-tools/bin/python -m pip install \
  --require-hashes --only-binary=:all: -r tools/ci/rendering/requirements.txt
/tmp/chromium-rendering-tools/bin/python -m tools.ci.check_rendering \
  /path/to/browser/bundle --output /tmp/chromium-rendering
```

`tools/ci/chromium.py smoke` runs these checks after the existing browser smoke.
Native GitHub jobs upload `*.actual.png`, `*.expected.png`, amplified pixel
differences, browser logs and `report.json`, including failed checks.

To refresh baselines, run the command above with `--update-baselines`, inspect
both actual screenshots and the diffs, then commit the two PNGs and provenance
file. CI never refreshes baselines. Initial references came from the validated
Bazel-built Chromium 142.0.7444.59 Linux amd64 artifact; other native platforms
remain unverified until their browser ports build.
