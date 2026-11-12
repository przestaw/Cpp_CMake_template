# ==== PKG-CONFIG IMPORTED TARGETS ====
# Prefer PkgConfig:: imported targets over copying host-specific -D/-I/-l flags
# from a single distribution's compiler command line.
find_package(PkgConfig REQUIRED)
pkg_check_modules(DEMO_XMLSEC REQUIRED IMPORTED_TARGET xmlsec1)
pkg_check_modules(DEMO_XMLSEC_OPENSSL REQUIRED IMPORTED_TARGET xmlsec1-openssl)

# Keep PRIVATE unless the public headers of document_signer include xmlsec headers.
target_link_libraries(document_signer PRIVATE
    PkgConfig::DEMO_XMLSEC
    PkgConfig::DEMO_XMLSEC_OPENSSL
)
