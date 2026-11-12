# ==== CUSTOM FORM & HEADER CODEGEN BEFORE AUTOMOC / AUTOUIC ====
# Reference pattern for a build-time generator (`form_generator`) that loads custom
# Designer widget plugins (`designer_widgets`) and emits C++, Q_OBJECT headers, and .ui files.
set(form_dir "${CMAKE_CURRENT_BINARY_DIR}/generated/forms")
set(outputs
    "${form_dir}/panel.cpp"
    "${form_dir}/panel.h"
    "${form_dir}/panel.ui"
    "${form_dir}/bundle_api.h"
)

# List all compilation-driving files in OUTPUT (keep shared headers single-owned);
# use BYPRODUCTS only for auxiliary non-compiled artifacts.
add_custom_command(
    OUTPUT ${outputs}
    COMMAND "${CMAKE_COMMAND}" -E make_directory "${form_dir}"
    COMMAND "${CMAKE_COMMAND}" -E env
        "QT_PLUGIN_PATH=${CMAKE_BINARY_DIR}/tool-plugins"
        "$<TARGET_FILE:form_generator>" "${schema}" "${form_dir}"
    DEPENDS form_generator designer_widgets "${schema}"
    BYPRODUCTS "${form_dir}/panel-documentation.xml"
    VERBATIM
)

add_custom_target(panel_forms DEPENDS ${outputs})
target_sources(panel PRIVATE ${outputs})

# Ensure generated Q_OBJECT headers and .ui forms exist before panel_autogen runs.
set_property(TARGET panel APPEND PROPERTY AUTOGEN_TARGET_DEPENDS panel_forms)
set_property(TARGET panel APPEND PROPERTY AUTOUIC_SEARCH_PATHS "${form_dir}")
target_include_directories(panel PRIVATE "${form_dir}")
