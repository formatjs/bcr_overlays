chromium::import! {
    "//build/rust/allocator" as allocator;
}

#[cxx::bridge(namespace = "native_test")]
mod ffi {
    unsafe extern "C++" {
        include!("bcr_test/cxx_bridge_types.h");
        fn cpp_reverse(input: &str) -> UniquePtr<CxxString>;
    }
    extern "Rust" {
        fn rust_sum(values: &[u64]) -> u64;
        fn roundtrip(input: &str) -> String;
        fn normalize_json(input: &str, lenient: bool) -> String;
    }
}

fn rust_sum(values: &[u64]) -> u64 {
    values.iter().sum()
}

fn roundtrip(input: &str) -> String {
    ffi::cpp_reverse(input).to_str().unwrap().to_owned()
}

fn normalize_json(input: &str, lenient: bool) -> String {
    use serde::Deserialize;
    use serde_json_lenient::{Deserializer, Value};
    use serde_json_lenient::de::SliceRead;

    let mut parser = Deserializer::new(SliceRead::new(
        input.as_bytes(), lenient, false, false, false, lenient,
    ));
    parser.set_allow_comments(lenient);
    parser.set_ignore_trailing_commas(lenient);
    match Value::deserialize(&mut parser) {
        Ok(value) if parser.end().is_ok() => serde_json_lenient::to_string(&value).unwrap(),
        _ => String::new(),
    }
}
