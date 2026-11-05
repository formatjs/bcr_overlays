chromium::import! {
    "//build/rust/allocator" as allocator;
}

#[unsafe(no_mangle)]
pub extern "C" fn chromium_base_test_emit_log() {
    log::warn!("native Rust logging {}", 142);
}
