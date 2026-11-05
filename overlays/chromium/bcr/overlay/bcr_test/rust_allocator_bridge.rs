chromium::import! {
    "//build/rust/allocator" as allocator;
}

#[repr(C, align(64))]
struct Buffer([u8; 4096]);

#[unsafe(no_mangle)]
pub extern "C" fn rust_allocation_new() -> *mut u8 {
    let buffer = Box::into_raw(Box::new(Buffer([0x2a; 4096])));
    unsafe { std::ptr::addr_of_mut!((*buffer).0).cast() }
}

#[unsafe(no_mangle)]
pub unsafe extern "C" fn rust_allocation_free(pointer: *mut u8) {
    drop(unsafe { Box::from_raw(pointer.cast::<Buffer>()) });
}

#[unsafe(no_mangle)]
pub extern "C" fn rust_reject_unsupported_alignment() -> bool {
    let layout = std::alloc::Layout::from_size_align(64, 1 << 30).unwrap();
    let pointer = unsafe { std::alloc::alloc(layout) };
    if pointer.is_null() {
        true
    } else {
        unsafe { std::alloc::dealloc(pointer, layout) };
        false
    }
}

#[unsafe(no_mangle)]
pub extern "C" fn rust_vec_roundtrip() -> bool {
    let mut values = Vec::with_capacity(1);
    for value in 0..8192_u64 {
        values.push(value * 3);
    }
    values.iter().enumerate().all(|(index, value)| *value == index as u64 * 3)
}

#[unsafe(no_mangle)]
pub extern "C" fn rust_allocation_failure() -> ! {
    std::alloc::handle_alloc_error(std::alloc::Layout::from_size_align(4096, 64).unwrap())
}
