"""Qt 5 -> Qt 6 readiness: module availability, build-model checks and a source scan.

Module data are guidance. The authoritative answer for "is module X available" is
the target Qt installation itself: pass --qt6-qmake (or --qt6-cmake-dir) and the
installed Qt6<Module>Config.cmake files are checked.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from qmigrate.model import model_files
from qmigrate.report import Findings

# qmake QT name -> (Qt 6 CMake component or None, available since 6.x, note)
QT6_MODULES = {
    'core': ('Core', '6.0', ''), 'gui': ('Gui', '6.0', ''), 'widgets': ('Widgets', '6.0', ''),
    'network': ('Network', '6.0', ''), 'sql': ('Sql', '6.0', ''), 'xml': ('Xml', '6.0', 'SAX classes moved to Core5Compat'),
    'concurrent': ('Concurrent', '6.0', ''), 'printsupport': ('PrintSupport', '6.0', ''),
    'dbus': ('DBus', '6.0', ''), 'testlib': ('Test', '6.0', ''),
    'opengl': ('OpenGL', '6.0', 'QGL* classes removed; QOpenGL* helpers moved here from Gui; QOpenGLWidget is in OpenGLWidgets'),
    'svg': ('Svg', '6.0', 'QSvgWidget and QGraphicsSvgItem moved to SvgWidgets'),
    'qml': ('Qml', '6.0', ''), 'quick': ('Quick', '6.0', ''), 'quickwidgets': ('QuickWidgets', '6.0', ''),
    'quickcontrols2': ('QuickControls2', '6.0', ''), 'help': ('Help', '6.0', ''), 'uitools': ('UiTools', '6.0', ''),
    'designer': ('Designer', '6.0', ''), 'quick3d': ('Quick3D', '6.0', ''),
    'charts': ('Charts', '6.1', ''), 'datavisualization': ('DataVisualization', '6.1', ''),
    'networkauth': ('NetworkAuth', '6.1', ''), 'scxml': ('Scxml', '6.1', 'QStateMachine moved to StateMachine'),
    'virtualkeyboard': ('VirtualKeyboard', '6.1', ''), 'axcontainer': ('AxContainer', '6.1', ''),
    'axserver': ('AxServer', '6.1', ''), '3dcore': ('3DCore', '6.1', ''), '3drender': ('3DRender', '6.1', ''),
    '3dinput': ('3DInput', '6.1', ''), '3dlogic': ('3DLogic', '6.1', ''), '3dextras': ('3DExtras', '6.1', ''),
    '3danimation': ('3DAnimation', '6.1', ''),
    'bluetooth': ('Bluetooth', '6.2', 'QML API and some classes removed'),
    'multimedia': ('Multimedia', '6.2', 'public API substantially changed'),
    'multimediawidgets': ('MultimediaWidgets', '6.2', 'API changed'), 'nfc': ('Nfc', '6.2', ''),
    'positioning': ('Positioning', '6.2', ''), 'remoteobjects': ('RemoteObjects', '6.2', ''),
    'sensors': ('Sensors', '6.2', 'several sensor types removed'), 'serialbus': ('SerialBus', '6.2', 'class renames'),
    'serialport': ('SerialPort', '6.2', ''), 'webchannel': ('WebChannel', '6.2', ''),
    'webengine': ('WebEngineQuick', '6.2', 'Qt Quick module renamed to WebEngineQuick'),
    'webenginecore': ('WebEngineCore', '6.2', ''),
    'webenginewidgets': ('WebEngineWidgets', '6.2', 'QWebEnginePage and others moved to WebEngineCore'),
    'websockets': ('WebSockets', '6.2', ''), 'webview': ('WebView', '6.2', ''),
    'texttospeech': ('TextToSpeech', '6.4', ''), 'location': ('Location', '6.5', ''),
    'xmlpatterns': (None, None, 'removed; no direct replacement (consider QXmlStreamReader or a third-party XSLT/XQuery library)'),
    'script': (None, None, 'removed; use QJSEngine (Qml)'), 'scripttools': (None, None, 'removed'),
    'x11extras': (None, None, 'removed; QX11Info replaced by QNativeInterface (Qt 6.2+)'),
    'winextras': (None, None, 'removed; parts moved to QtGui (e.g. QWinTaskbar has no replacement)'),
    'macextras': (None, None, 'removed; parts moved to QtGui/QNativeInterface'),
    'gamepad': (None, None, 'removed'), 'purchasing': (None, None, 'removed'),
    'webkit': (None, None, 'removed long before Qt 6; use WebEngine'), 'webkitwidgets': (None, None, 'removed; use WebEngineWidgets'),
}

# Components that exist only in Qt 6 (a dual Qt 5/6 build needs them conditionally).
QT6_ONLY_COMPONENTS = {'Core5Compat', 'OpenGLWidgets', 'SvgWidgets', 'StateMachine', 'WebEngineQuick'}

CPP_EXT = ('.cpp', '.cc', '.cxx', '.c++', '.h', '.hh', '.hpp', '.hxx', '.ipp', '.inl', '.mm')

# id, regex, severity, message, Qt 6 component that restores or hosts the API (or None)
SOURCE_RULES = [
    ('qregexp', r'\bQRegExp(?:Validator)?\b', 'error', 'QRegExp removed from QtCore: port to QRegularExpression or use Core5Compat', 'Core5Compat'),
    ('qtextcodec', r'\bQTextCodec\b|\bQTextEncoder\b|\bQTextDecoder\b', 'error', 'QTextCodec removed from QtCore: QStringConverter, or Core5Compat', 'Core5Compat'),
    ('qlinkedlist', r'\bQLinkedList\b', 'error', 'QLinkedList removed: std::list, or Core5Compat', 'Core5Compat'),
    ('qstringref', r'\bQStringRef\b', 'error', 'QStringRef removed: QStringView, or Core5Compat', 'Core5Compat'),
    ('qxmlsax', r'\bQXml(?:SimpleReader|InputSource|DefaultHandler|ContentHandler|Reader|Attributes)\b', 'error',
     'SAX XML classes moved to Core5Compat: port to QXmlStreamReader', 'Core5Compat'),
    ('textstream-codec', r'\.setCodec\s*\(', 'error', 'QTextStream::setCodec removed: setEncoding(QStringConverter::...)', None),
    ('qdesktopwidget', r'\bQDesktopWidget\b|QApplication::desktop\s*\(', 'error', 'QDesktopWidget removed: QScreen / QGuiApplication::screens()', None),
    ('qrand', r'\bqs?rand\s*\(', 'error', 'qrand()/qsrand() removed: QRandomGenerator', None),
    ('qmatrix', r'\bQMatrix\b', 'error', 'QMatrix removed: QTransform', None),
    ('qtalgorithms', r'\bq(?:Sort|StableSort|Find|LowerBound|UpperBound|BinaryFind|Copy|CopyBackward|Fill|Equal|Count|Greater|Less)\s*[<(]', 'error',
     'deprecated QtAlgorithms functions removed: use std algorithms', None),
    ('split-behavior', r'QString::(?:SkipEmptyParts|KeepEmptyParts)', 'error', 'use Qt::SkipEmptyParts / Qt::KeepEmptyParts (available since 5.14)', None),
    ('insertmulti', r'\.insertMulti\s*\(', 'error', 'QHash/QMap insertMulti removed: QMultiHash / QMultiMap', None),
    ('qvariant-type', r'\bQVariant::(?:Type\b|Int\b|String\b|Bool\b|Double\b|List\b|Map\b|Invalid\b|UserType\b)', 'warning',
     'QVariant::Type is deprecated: QMetaType / typeId()', None),
    ('qvariant-helpers', r'\bqVariant(?:Value|FromValue|CanConvert|SetValue)\s*[<(]', 'error', 'qVariantValue & co. removed: QVariant::value/fromValue/canConvert', None),
    ('midbutton', r'\bQt::MidButton\b', 'error', 'Qt::MidButton removed: Qt::MiddleButton', None),
    ('qstring-sprintf', r'\.sprintf\s*\(|QString::sprintf\b', 'error', 'QString::sprintf removed: QString::asprintf or arg()', None),
    ('fontmetrics-width', r'(?:fontMetrics\s*\(\s*\)|\bfm|Metrics)\.width\s*\(', 'warning', 'QFontMetrics::width removed: horizontalAdvance (5.11+)', None),
    ('highdpi-attr', r'Qt::AA_(?:EnableHighDpiScaling|UseHighDpiPixmaps|DisableHighDpiScaling)', 'warning', 'high-DPI scaling is always on in Qt 6; the attribute has no effect', None),
    ('qsound', r'\bQSound\b', 'error', 'QSound removed: QSoundEffect (Multimedia 6.2+)', 'Multimedia'),
    ('qgl', r'\bQGL(?:Widget|Format|Context|Shader|ShaderProgram|FramebufferObject|PixelBuffer|Buffer|Functions)\b', 'error',
     'legacy QGL classes removed: QOpenGLWidget / QOpenGL* classes', 'OpenGLWidgets'),
    ('qopenglwidget', r'\bQOpenGLWidget\b', 'info', 'QOpenGLWidget moved to the OpenGLWidgets module', 'OpenGLWidgets'),
    ('qopengl-helpers', r'\bQOpenGL(?:Buffer|Shader|ShaderProgram|VertexArrayObject|Texture|FramebufferObject|Debug\w*|Timer\w*|PaintDevice|Window|TextureBlitter)\b',
     'info', 'QOpenGL* helper classes moved from Gui to the OpenGL module', 'OpenGL'),
    ('qsvgwidget', r'\bQSvgWidget\b|\bQGraphicsSvgItem\b', 'info', 'moved to the SvgWidgets module', 'SvgWidgets'),
    ('statemachine', r'\bQ(?:StateMachine|State|FinalState|HistoryState|SignalTransition|EventTransition|KeyEventTransition|MouseEventTransition)\b',
     'info', 'state machine classes moved to the StateMachine module', 'StateMachine'),
    ('qscript', r'\bQScript(?:Engine|Value|Context)\b', 'error', 'Qt Script removed: QJSEngine', None),
    ('network-session', r'\bQNetwork(?:ConfigurationManager|Configuration|Session)\b', 'error', 'bearer management removed: QNetworkInformation (6.1+)', None),
    ('qdirmodel', r'\bQDirModel\b', 'error', 'QDirModel removed: QFileSystemModel', None),
    ('grab', r'QPixmap::grab(?:Widget|Window)\b', 'error', 'use QWidget::grab / QScreen::grabWindow', None),
    ('style-option-v', r'\bQStyleOption\w*V[2-4]\b', 'error', 'versioned QStyleOption*V2..V4 types removed', None),
    ('toset', r'\.toSet\s*\(\s*\)', 'warning', 'QList::toSet removed: QSet(begin, end)', None),
    ('qdatetime-from-date', r'\bQDateTime\s*\(\s*QDate\b', 'warning', 'QDateTime(const QDate&) removed: QDate::startOfDay()', None),
    ('q-enums', r'\bQ_ENUMS\s*\(', 'info', 'Q_ENUMS is deprecated: Q_ENUM', None),
    ('compat-include', r'#\s*include\s*[<"]Qt(?:Core|Xml)/(?:QRegExp|QTextCodec|QTextEncoder|QTextDecoder|QLinkedList|QStringRef|QXml(?:SimpleReader|InputSource|DefaultHandler|Reader))[>"]',
     'error', 'in Qt 6 this header lives in QtCore5Compat: include it without the module prefix (<QRegExp>) so both Qt 5 and Qt 6 resolve it', 'Core5Compat'),
    ('qml-controls1', r'^\s*import\s+QtQuick\.Controls\s+1\.', 'error', 'Qt Quick Controls 1 removed: Controls 2', None),
    ('qml-graphical-effects', r'^\s*import\s+QtGraphicalEffects', 'error', 'use import Qt5Compat.GraphicalEffects (or MultiEffect, 6.5+)', 'Core5Compat'),
    ('qml-dialogs1', r'^\s*import\s+QtQuick\.Dialogs\s+1\.', 'warning', 'QtQuick.Dialogs API changed in Qt 6', None),
]
_COMPILED = [(i, re.compile(p, re.M), s, m, c) for i, p, s, m, c in SOURCE_RULES]


def version_tuple(text: str) -> tuple:
    return tuple(int(x) for x in re.findall(r'\d+', text)[:2]) or (0,)


def installed_qt6_components(qmake: str | None = None, cmake_dir: Path | None = None) -> tuple[set, str]:
    """Components of an installed Qt 6, from its Qt6<Component>Config.cmake files."""
    version = ''
    if qmake:
        out = subprocess.run([qmake, '-query'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             timeout=60, check=True).stdout.decode()
        query = dict(line.split(':', 1) for line in out.splitlines() if ':' in line)
        version = query.get('QT_VERSION', '')
        cmake_dir = Path(query['QT_INSTALL_LIBS']) / 'cmake'
        if not cmake_dir.is_dir():
            cmake_dir = Path(query['QT_INSTALL_PREFIX']) / 'lib' / 'cmake'
    components = set()
    if cmake_dir and cmake_dir.is_dir():
        for config in cmake_dir.glob('Qt6*/Qt6*Config.cmake'):
            name = config.parent.name[3:]
            if config.name == f'Qt6{name}Config.cmake' and name and not name.endswith(('Tools', 'Private')):
                components.add(name)
    return components, version


def strip_comments(text: str) -> str:
    text = re.sub(r'/\*.*?\*/', lambda m: '\n' * m.group(0).count('\n'), text, flags=re.S)
    return re.sub(r'//[^\n]*', '', text)


def scan_file(path: Path) -> list[tuple]:
    try:
        text = path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return []
    is_qml = path.suffix == '.qml'
    if not is_qml:
        text = strip_comments(text)
    hits = []
    for rule_id, regex, severity, message, component in _COMPILED:
        if rule_id.startswith('qml-') != is_qml:
            continue
        for match in regex.finditer(text):
            line = text.count('\n', 0, match.start()) + 1
            hits.append((rule_id, severity, message, component, line, match.group(0).strip()))
    return hits


def check(model: dict, records: dict, *, target: str, installed: set | None = None,
          extra_files: list[Path] = (), findings: Findings | None = None) -> tuple[Findings, dict]:
    """Return findings and {project source: sorted Qt 6 components it additionally needs}."""
    findings = findings or Findings()
    target_v = version_tuple(target)
    needs: dict[str, set] = {}
    source_root = Path(model['sourceRoot'])
    seen_files: dict[Path, str] = {}
    for source, record in sorted(records.items()):
        v = record['vars']
        windows = any(s in record.get('meta', {}).get('xspec', '') for s in ('msvc', 'win32'))
        for module in v.get('QT', []) + v.get('QT_PRIVATE', []):
            name = module[:-len('-private')] if module.endswith('-private') else module
            entry = QT6_MODULES.get(name)
            if module.endswith('-private'):
                findings.add(source, 'warning', 'qt6.private-module',
                             f'QT += {module}: private Qt API changes between minor releases; re-check every use')
            if entry is None:
                findings.add(source, 'warning', 'qt6.unknown-module', f'QT += {module}: not in the module table; check manually')
                continue
            component, since, note = entry
            if component is None:
                findings.add(source, 'error', 'qt6.removed-module', f'QT += {module}: {note}')
                continue
            if version_tuple(since) > target_v:
                findings.add(source, 'error', 'qt6.module-too-new',
                             f'QT += {module}: {component} returned in Qt {since}; target is {target}')
            if installed is not None and component not in installed:
                findings.add(source, 'error', 'qt6.module-not-installed',
                             f'{component} is not installed in the target Qt 6')
            if note:
                findings.add(source, 'info', 'qt6.module-note', f'{module} -> Qt6::{component}: {note}')
        config = v.get('CONFIG', [])
        standards = [s for s in config if re.fullmatch(r'c\+\+(11|14|0x|1y)', s)]
        explicit_std = [f for f in v.get('QMAKE_CXXFLAGS', []) if re.match(r'^(-std=|[-/]std:)(c|gnu)\+\+(98|03|11|14|0x|1y)$', f)]
        if standards or explicit_std:
            findings.add(source, 'error', 'qt6.cxx-standard',
                         f'{" ".join(standards + explicit_std)}: Qt 6 targets require C++17 (Qt6::Platform cxx_std_17)')
        if windows:
            findings.add(source, 'warning', 'qt6.msvc-permissive',
                         'Qt 6 adds -Zc:__cplusplus -permissive- to every consumer on MSVC: code relying on '
                         'permissive-mode extensions or a wrong __cplusplus check stops compiling')
        if 'qtquickcompiler' in config:
            findings.add(source, 'info', 'qt6.quickcompiler', 'CONFIG qtquickcompiler: use qt_add_qml_module() in Qt 6')
        for d in v.get('DEFINES', []):
            m = re.match(r'QT_DISABLE_DEPRECATED_BEFORE=(0x[0-9A-Fa-f]+)', d)
            if m and int(m.group(1), 16) < 0x050F00:
                findings.add(source, 'info', 'qt6.deprecation-level',
                             f'{d}: build once on Qt 5.15 with 0x050F00 to turn API removed in Qt 6 into compile errors '
                             '(Qt 6.5+ names it QT_DISABLE_DEPRECATED_UP_TO)')
        for path in model_files(record, ('SOURCES', 'HEADERS', 'OBJECTIVE_SOURCES', 'OTHER_FILES', 'DISTFILES')):
            if path.suffix in CPP_EXT + ('.qml',):
                seen_files.setdefault(path.resolve(), source)
    for path in extra_files:
        seen_files.setdefault(Path(path).resolve(), '(source tree)')
    for path, source in sorted(seen_files.items()):
        try:
            shown = path.relative_to(source_root).as_posix()
        except ValueError:
            shown = str(path)
        for rule_id, severity, message, component, line, text in scan_file(path):
            findings.add(source, severity, f'qt6.api.{rule_id}', message, location=f'{shown}:{line}', evidence=text)
            if component and source != '(source tree)':
                needs.setdefault(source, set()).add(component)
    for source, components in needs.items():
        if installed is not None:
            for component in sorted(components - installed):
                findings.add(source, 'error', 'qt6.module-not-installed', f'{component} needed by the source scan is not installed')
        findings.add(source, 'info', 'qt6.extra-components',
                     'additional Qt 6 components: ' + ', '.join(sorted(components)))
    return findings, {k: sorted(v) for k, v in needs.items()}
