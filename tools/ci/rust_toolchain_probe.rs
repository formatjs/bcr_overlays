#![feature(linkage)]

#[linkage = "weak"]
#[no_mangle]
pub static CHROMIUM_RUST_PROBE: u8 = 42;

fn main() {
    assert_eq!(CHROMIUM_RUST_PROBE, 42);
    let values: Vec<_> = (0..4).map(|value| value * 2).collect();
    assert_eq!(values, [0, 2, 4, 6]);
    println!("{} {}", std::env::consts::OS, std::env::consts::ARCH);
}
