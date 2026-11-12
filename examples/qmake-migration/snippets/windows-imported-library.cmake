# ==== WINDOWS SHARED IMPORTED TARGET (.dll + .lib) ====
# On Windows, SHARED IMPORTED targets require both IMPORTED_LOCATION_<CONFIG> (.dll)
# and IMPORTED_IMPLIB_<CONFIG> (.lib), plus explicit RelWithDebInfo mapping when the
# vendor SDK ships only Debug and Release binaries.
add_library(Vendor::Transport SHARED IMPORTED)
set_target_properties(Vendor::Transport PROPERTIES
    IMPORTED_CONFIGURATIONS "DEBUG;RELEASE"
    IMPORTED_LOCATION_RELEASE "${TRANSPORT_ROOT}/bin/transport.dll"
    IMPORTED_IMPLIB_RELEASE "${TRANSPORT_ROOT}/lib/transport.lib"
    IMPORTED_LOCATION_DEBUG "${TRANSPORT_ROOT}/bin/transportd.dll"
    IMPORTED_IMPLIB_DEBUG "${TRANSPORT_ROOT}/lib/transportd.lib"
    MAP_IMPORTED_CONFIG_RELWITHDEBINFO Release
    INTERFACE_INCLUDE_DIRECTORIES "${TRANSPORT_ROOT}/include"
)

target_link_libraries(network_component PRIVATE Vendor::Transport)
