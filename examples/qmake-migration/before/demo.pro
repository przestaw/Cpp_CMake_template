# ==== SUBDIRS TOPOLOGY ====
# NOTE: qmake orders build subdirectories via `.depends`; CMake expresses both
# build order and usage propagation directly via `target_link_libraries()`.
TEMPLATE = subdirs
SUBDIRS += core app
app.depends = core
