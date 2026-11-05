"""Chromium ICU's shared and implementation-only GN configuration."""

ICU_DEFINES = [
    "U_USING_ICU_NAMESPACE=0",
    "U_ENABLE_DYLOAD=0",
    "USE_CHROMIUM_ICU=1",
    "U_ENABLE_TRACING=1",
    "U_ENABLE_RESOURCE_TRACING=0",
    "U_STATIC_IMPLEMENTATION",
]

ICU_CODE_DEFINES = [
    "HAVE_DLOPEN=0",
    "UCONFIG_ONLY_HTML_CONVERSION=1",
    "UCONFIG_USE_ML_PHRASE_BREAKING=1",
    "UCONFIG_USE_WINDOWS_LCID_MAPPING_API=0",
    "U_CHARSET_IS_UTF8=1",
]

ICU_COPTS = [
    "-std=c++20",
    "-frtti",
    "-pthread",
    "-Wno-parentheses",
    "-Wno-unused-function",
    "-Wno-unused-variable",
    "-Wno-ambiguous-reversed-operator",
    "-Wno-deprecated-declarations",
]
