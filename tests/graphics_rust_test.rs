use skrifa::{
    instance::{LocationRef, Size},
    outline::{DrawSettings, OutlinePen},
    FontRef, MetadataProvider,
};
use std::{env, fs, io::Cursor, path::PathBuf};

#[derive(Default)]
struct Path {
    points: Vec<(f32, f32)>,
    closed: usize,
}

impl OutlinePen for Path {
    fn move_to(&mut self, x: f32, y: f32) {
        self.points.push((x, y));
    }
    fn line_to(&mut self, x: f32, y: f32) {
        self.points.push((x, y));
    }
    fn quad_to(&mut self, cx: f32, cy: f32, x: f32, y: f32) {
        self.points.extend([(cx, cy), (x, y)]);
    }
    fn curve_to(&mut self, ax: f32, ay: f32, bx: f32, by: f32, x: f32, y: f32) {
        self.points.extend([(ax, ay), (bx, by), (x, y)]);
    }
    fn close(&mut self) {
        self.closed += 1;
    }
}

fn font_outlines() {
    let runfiles = PathBuf::from(env::var_os("TEST_SRCDIR").unwrap())
        .join(env::var_os("TEST_WORKSPACE").unwrap());
    let bytes = fs::read(runfiles.join(env!("FONT_FIXTURE"))).unwrap();
    let font = FontRef::new(&bytes).unwrap();
    let id = font.charmap().map('A').unwrap();
    let size = Size::new(20.0);
    let location = LocationRef::default();
    let advance = font.glyph_metrics(size, location).advance_width(id).unwrap();
    assert!((advance - 20.0).abs() < 0.0001);
    let outlines = font.outline_glyphs();
    let glyph = outlines.get(id).unwrap();
    let mut path = Path::default();
    glyph
        .draw(DrawSettings::unhinted(size, location), &mut path)
        .unwrap();
    assert_eq!(path.closed, 1);
    assert!(path.points.len() >= 4);
    let bounds = path.points.iter().fold(
        (f32::INFINITY, f32::INFINITY, f32::NEG_INFINITY, f32::NEG_INFINITY),
        |(left, bottom, right, top), &(x, y)| {
            (left.min(x), bottom.min(y), right.max(x), top.max(y))
        },
    );
    for (actual, expected) in [bounds.0, bounds.1, bounds.2, bounds.3]
        .into_iter()
        .zip([0.0, -4.0, 20.0, 16.0])
    {
        assert!((actual - expected).abs() < 0.0001);
    }
    assert!(FontRef::new(&bytes[..12]).is_err());
    let mut corrupt = bytes;
    corrupt[..4].copy_from_slice(b"NOPE");
    assert!(FontRef::new(&corrupt).is_err());
}

fn png_pixels() {
    // Independent PNG fixture: RGB, two pixels, filter 0, zlib stored block.
    const IMAGE: &[u8] = &[
        137, 80, 78, 71, 13, 10, 26, 10, 0, 0, 0, 13, 73, 72,
        68, 82, 0, 0, 0, 2, 0, 0, 0, 1, 8, 2, 0, 0,
        0, 123, 64, 232, 221, 0, 0, 0, 18, 73, 68, 65, 84, 120,
        1, 1, 7, 0, 248, 255, 0, 255, 0, 0, 0, 255, 0, 7,
        255, 1, 255, 197, 14, 226, 106, 0, 0, 0, 0, 73, 69, 78,
        68, 174, 66, 96, 130,
    ];
    let mut reader = png::Decoder::new(Cursor::new(IMAGE)).read_info().unwrap();
    let mut pixels = vec![0; reader.output_buffer_size()];
    let info = reader.next_frame(&mut pixels).unwrap();
    assert_eq!(
        (info.width, info.height, info.color_type),
        (2, 1, png::ColorType::Rgb),
    );
    assert_eq!(&pixels[..info.buffer_size()], &[255, 0, 0, 0, 255, 0]);
    let mut corrupt = IMAGE.to_vec();
    // Change only IDAT CRC; leave compressed pixels and Adler checksum intact.
    corrupt[59] ^= 0x40;
    let mut reader = png::Decoder::new(Cursor::new(corrupt)).read_info().unwrap();
    assert!(reader.next_frame(&mut pixels).is_err());
    let mut reader = png::Decoder::new(Cursor::new(&IMAGE[..50])).read_info().unwrap();
    assert!(reader.next_frame(&mut pixels).is_err());
}

fn main() {
    font_outlines();
    png_pixels();
}
