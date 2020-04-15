file(GLOB ERROR_INC "${PROJECT_SOURCE_DIR}/include/error/*.h")
file(GLOB LIB_INC "${PROJECT_SOURCE_DIR}/include/*.h")

include_directories("error")

set(LIB_INC ${LIB_INC} ${PARSER_INC} ${SCANNER_INC} ${ERROR_INC} PARENT_SCOPE)