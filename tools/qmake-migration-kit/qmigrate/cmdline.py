"""Parse recorded compiler, linker and archiver command lines into comparable facts.

Dialects: GCC/Clang driver, MSVC cl/clang-cl, MSVC link/lib, GNU-style ar.
Unrecognised options are kept verbatim in `other`, never dropped.
"""
from __future__ import annotations

import ntpath
import os
import posixpath
import re
import shlex

LAUNCHERS = {'ccache', 'sccache', 'distcc', 'icecc', 'buildcache'}
SOURCE_EXT = {'.c': 'c', '.cc': 'cxx', '.cpp': 'cxx', '.cxx': 'cxx', '.c++': 'cxx', '.cp': 'cxx', '.C': 'cxx',
              '.m': 'objc', '.mm': 'objcxx', '.s': 'asm', '.S': 'asm', '.asm': 'asm'}
GCC_ARG_OPTIONS = {'-o', '-MF', '-MT', '-MQ', '-x', '-include', '-imacros', '-isystem', '-iquote', '-idirafter',
                   '-isysroot', '-arch', '-target', '-Xclang', '-mllvm', '-Xlinker', '-Xassembler',
                   '-Xpreprocessor', '-D', '-U', '-I', '-L', '-l', '-framework', '-Xarch_x86_64', '-Xarch_arm64',
                   '-iprefix', '-iwithprefix', '-iwithprefixbefore', '-aux-info', '-dumpbase'}
NOISE = {'-pipe', '-c', '-MD', '-MMD', '-MP', '-fdiagnostics-color', '-fdiagnostics-color=always',
         '-fcolor-diagnostics', '-fno-color-diagnostics', '/nologo', '-nologo', '/FS', '-FS', '/showIncludes',
         '-showIncludes', '/c', '-c', '/NOLOGO', '-NOLOGO'}
MSVC_NOISE = {'/nologo', '-nologo', '/FS', '-FS', '/showIncludes', '-showIncludes', '/NOLOGO', '-NOLOGO'}
STD_ALIASES = {'0x': '11', '1y': '14', '1z': '17', '2a': '20', '2b': '23', '2c': '26'}


def split_response(text: str, windows: bool) -> list[str]:
    if not windows:
        try:
            return shlex.split(text, posix=True)
        except ValueError:
            return text.split()
    return windows_split(text)


def windows_split(text: str) -> list[str]:
    """CommandLineToArgvW-style splitting (backslashes before quotes, toggled quoting)."""
    args, current, in_quotes, has_arg, i = [], [], False, False, 0
    while i < len(text):
        ch = text[i]
        if ch == '\\':
            j = i
            while j < len(text) and text[j] == '\\':
                j += 1
            count = j - i
            if j < len(text) and text[j] == '"':
                current.append('\\' * (count // 2))
                if count % 2:
                    current.append('"')
                    i = j + 1
                else:
                    i = j
                has_arg = True
                continue
            current.append('\\' * count)
            i = j
            has_arg = True
            continue
        if ch == '"':
            in_quotes = not in_quotes
            has_arg = True
        elif ch in ' \t\r\n' and not in_quotes:
            if has_arg:
                args.append(''.join(current))
                current, has_arg = [], False
        else:
            current.append(ch)
            has_arg = True
        i += 1
    if has_arg:
        args.append(''.join(current))
    return args


def strip_launchers(argv: list[str]) -> list[str]:
    while argv and tool_name(argv[0]) in LAUNCHERS:
        argv = argv[1:]
    return argv


def tool_name(path: str) -> str:
    name = ntpath.basename(posixpath.basename(path)).lower()
    return name[:-4] if name.endswith('.exe') else name


def dialect(argv: list[str], kind: str) -> str:
    name = tool_name(argv[0]) if argv else ''
    if name in ('cl', 'clang-cl'):
        return 'msvc'
    if name in ('link', 'lld-link'):
        return 'msvc-link'
    if name in ('lib', 'llvm-lib'):
        return 'msvc-lib'
    if kind == 'ar' or name == 'ar' or name.endswith('-ar') or name == 'llvm-ar':
        return 'ar'
    return 'gcc'


def expand(argv: list[str], responses: dict, windows: bool) -> list[str]:
    out = []
    for arg in argv:
        if arg in responses:
            out += split_response(responses[arg], windows)
        else:
            out.append(arg)
    return out


def absolute(path: str, cwd: str, windows: bool) -> str:
    mod = ntpath if windows else posixpath
    if not mod.isabs(path):
        path = mod.join(cwd, path)
    path = mod.normpath(path)
    return path.replace('\\', '/') if windows else path


def parse_define(text: str, msvc: bool) -> tuple[str, str | None]:
    if msvc and '#' in text and '=' not in text.split('#', 1)[0]:
        name, value = text.split('#', 1)
        return name, value
    if '=' in text:
        name, value = text.split('=', 1)
        return name, value
    return text, None


def norm_std(value: str) -> str:
    m = re.match(r'(c|gnu)\+\+(\w+)$', value)
    if not m:
        return value
    return f'{m.group(1)}++{STD_ALIASES.get(m.group(2), m.group(2))}'


def empty_compile() -> dict:
    return dict(sources=[], output=None, defines=[], undefs=[], includes=[], forcedIncludes=[], std=None,
                opt=[], debug=[], pic=[], runtime=None, warnings=[], other=[], preprocessOnly=False,
                compileOnly=False, lang=None)


def parse_compile(argv: list[str], cwd: str, *, responses: dict | None = None) -> dict:
    argv = strip_launchers(list(argv))
    d = dialect(argv, 'cxx')
    windows = d == 'msvc' or bool(re.match(r'^[A-Za-z]:[\\/]', cwd))
    args = expand(argv[1:], responses or {}, windows)
    result = empty_compile()
    result['tool'] = tool_name(argv[0]) if argv else ''
    result['dialect'] = d
    if d == 'msvc':
        _parse_msvc_compile(args, cwd, result)
    else:
        _parse_gcc_compile(args, cwd, result, windows)
    if result['lang'] is None and result['sources']:
        ext = os.path.splitext(result['sources'][0])[1]
        result['lang'] = SOURCE_EXT.get(ext, SOURCE_EXT.get(ext.lower(), 'other'))
    return result


def _parse_gcc_compile(args, cwd, r, windows):
    i = 0
    forced_lang = None
    while i < len(args):
        a = args[i]
        i += 1

        def value(prefix):
            nonlocal i
            if a == prefix:
                if i < len(args):
                    i += 1
                    return args[i - 1]
                return ''
            return a[len(prefix):]

        if a in ('-E', '-M', '-MM') or a.startswith('-dM'):
            r['preprocessOnly'] = True
        elif a == '-c':
            r['compileOnly'] = True
        elif a in NOISE:
            continue
        elif a.startswith('-o'):
            r['output'] = absolute(value('-o'), cwd, windows)
        elif a in ('-MF', '-MT', '-MQ'):
            i += 1
        elif a.startswith('-D'):
            r['defines'].append(parse_define(value('-D'), False))
        elif a.startswith('-U'):
            r['undefs'].append(value('-U'))
        elif a.startswith('-isystem'):
            r['includes'].append(dict(path=absolute(value('-isystem'), cwd, windows), kind='system'))
        elif a.startswith('-iquote'):
            r['includes'].append(dict(path=absolute(value('-iquote'), cwd, windows), kind='quote'))
        elif a.startswith('-idirafter'):
            r['includes'].append(dict(path=absolute(value('-idirafter'), cwd, windows), kind='after'))
        elif a.startswith('-I'):
            r['includes'].append(dict(path=absolute(value('-I'), cwd, windows), kind='user'))
        elif a in ('-include', '-imacros'):
            r['forcedIncludes'].append(absolute(value(a), cwd, windows))
        elif a.startswith('-std='):
            r['std'] = norm_std(a[5:])
        elif re.match(r'^-O[0-3sgzfast]*$', a):
            r['opt'].append(a)
        elif re.match(r'^-g', a):
            r['debug'].append(a)
        elif a in ('-fPIC', '-fpic', '-fPIE', '-fpie', '-fno-pic', '-fno-PIC', '-fno-pie', '-fno-PIE'):
            r['pic'].append(a)
        elif a == '-w' or (a.startswith('-W') and not re.match(r'^-W[lap],', a)):
            r['warnings'].append(a)
        elif a == '-x':
            forced_lang = value('-x')
            r['lang'] = {'c++': 'cxx', 'c': 'c', 'objective-c++': 'objcxx', 'objective-c': 'objc'}.get(forced_lang, forced_lang)
        elif a in GCC_ARG_OPTIONS:
            r['other'].append(f'{a} {args[i] if i < len(args) else ""}'.strip())
            i += 1
        elif not a.startswith('-'):
            ext = os.path.splitext(a)[1]
            if ext in SOURCE_EXT or ext.lower() in SOURCE_EXT or forced_lang:
                r['sources'].append(absolute(a, cwd, windows))
            else:
                r['other'].append(a)
        else:
            r['other'].append(a)


def _parse_msvc_compile(args, cwd, r):
    i = 0
    while i < len(args):
        a = args[i]
        i += 1
        if not a or a[0] not in '/-':
            ext = os.path.splitext(a)[1].lower()
            if ext in SOURCE_EXT:
                r['sources'].append(absolute(a, cwd, True))
            else:
                r['other'].append(a)
            continue
        o = a[1:]

        def value(prefix):
            nonlocal i
            rest = o[len(prefix):]
            if rest.startswith(':'):
                rest = rest[1:]
            if rest == '' and i < len(args):
                i += 1
                return args[i - 1]
            return rest

        if o == 'c':
            r['compileOnly'] = True
        elif o in ('MD', 'MDd', 'MT', 'MTd'):
            r['runtime'] = o
        elif a in MSVC_NOISE:
            continue
        elif o in ('E', 'EP', 'P'):
            r['preprocessOnly'] = True
        elif o.startswith('Fo'):
            r['output'] = absolute(value('Fo'), cwd, True)
        elif o.startswith(('Fd', 'Fp', 'Fa', 'FR', 'Fr', 'sourceDependencies')):
            continue
        elif o.startswith('D'):
            r['defines'].append(parse_define(value('D'), True))
        elif o.startswith('U') and not o.startswith('utf'):
            r['undefs'].append(value('U'))
        elif o.lower().startswith('external:i'):
            r['includes'].append(dict(path=absolute(value(o[:len('external:I')]), cwd, True), kind='system'))
        elif o.startswith('imsvc'):
            r['includes'].append(dict(path=absolute(value('imsvc'), cwd, True), kind='system'))
        elif o.startswith('I'):
            r['includes'].append(dict(path=absolute(value('I'), cwd, True), kind='user'))
        elif o.startswith('FI'):
            r['forcedIncludes'].append(absolute(value('FI'), cwd, True))
        elif o.startswith('std:'):
            r['std'] = norm_std(o[4:].replace('c++', 'c++'))
        elif re.match(r'^O[12dxsitby]', o):
            r['opt'].append('/' + o)
        elif o in ('Z7', 'Zi', 'ZI') or o.startswith('DEBUG'):
            r['debug'].append('/' + o)
        elif o in ('MD', 'MDd', 'MT', 'MTd'):
            r['runtime'] = o
        elif re.match(r'^(W[0-4]|Wall|WX-?|wd\d+|we\d+|wo\d+|w[1-4]\d+|w)$', o) or o.startswith('external:W'):
            r['warnings'].append('/' + o)
        elif o.startswith(('Tp', 'Tc')):
            src = value(o[:2])
            r['sources'].append(absolute(src, cwd, True))
            r['lang'] = 'cxx' if o.startswith('Tp') else 'c'
        elif o in ('TP', 'TC'):
            r['lang'] = 'cxx' if o == 'TP' else 'c'
        else:
            r['other'].append('/' + o)


def lib_identity(token: str) -> str:
    if token.startswith('-l'):
        return token[2:]
    base = ntpath.basename(posixpath.basename(token))
    base = re.sub(r'(\.so(\.\d+)*|\.a|\.lib|\.dll\.a|\.dylib|\.tbd)$', '', base)
    if base.startswith('lib') and len(base) > 3 and not token.lower().endswith('.lib'):
        base = base[3:]
    return base


def artifact_key(path: str) -> str:
    base = ntpath.basename(posixpath.basename(path))
    return re.sub(r'(\.so)(\.\d+)+$', r'\1', base)


def parse_link(argv: list[str], cwd: str, kind: str, *, responses: dict | None = None) -> dict:
    argv = strip_launchers(list(argv))
    d = dialect(argv, kind)
    windows = d.startswith('msvc') or bool(re.match(r'^[A-Za-z]:[\\/]', cwd))
    args = expand(argv[1:], responses or {}, windows)
    r = dict(tool=tool_name(argv[0]) if argv else '', dialect=d, output=None, kind='executable', objects=[],
             libs=[], libdirs=[], rpath=[], flags=[], preprocessOnly=False)
    if d == 'ar':
        r['kind'] = 'static'
        positional = [a for a in args if not a.startswith('-')]
        mode_skipped = positional[1:] if positional and not re.search(r'\.(a|lib)$', positional[0]) else positional
        for a in mode_skipped:
            if r['output'] is None and re.search(r'\.(a|lib)$', a):
                r['output'] = absolute(a, cwd, windows)
            else:
                r['objects'].append(absolute(a, cwd, windows))
        return r
    if d in ('msvc-link', 'msvc-lib'):
        if d == 'msvc-lib':
            r['kind'] = 'static'
        for a in args:
            o = a[1:] if a[:1] in '/-' else None
            upper = o.upper() if o else ''
            if o is None:
                low = a.lower()
                if low.endswith(('.obj', '.o', '.res')):
                    r['objects'].append(absolute(a, cwd, True))
                elif low.endswith('.lib'):
                    r['libs'].append(a)
                else:
                    r['flags'].append(a)
            elif upper.startswith('OUT:'):
                r['output'] = absolute(o[4:], cwd, True)
            elif upper.startswith('LIBPATH:'):
                r['libdirs'].append(absolute(o[8:], cwd, True))
            elif upper == 'DLL':
                r['kind'] = 'shared'
            elif upper.startswith(('PDB:', 'IMPLIB:', 'MANIFESTFILE:', 'ILK:', 'NOLOGO', 'MAP:')):
                continue
            else:
                r['flags'].append('/' + o)
        return r
    i = 0
    while i < len(args):
        a = args[i]
        i += 1
        if a in ('-o',) and i < len(args):
            r['output'] = absolute(args[i], cwd, windows)
            i += 1
        elif a.startswith('-o') and len(a) > 2:
            r['output'] = absolute(a[2:], cwd, windows)
        elif a == '-shared':
            r['kind'] = 'shared'
        elif a in ('-E', '-dM') or a.startswith('-dM'):
            r['preprocessOnly'] = True
        elif a.startswith('-L'):
            path = a[2:] or (args[i] if i < len(args) else '')
            if not a[2:]:
                i += 1
            r['libdirs'].append(absolute(path, cwd, windows))
        elif a.startswith('-l'):
            name = a[2:] or (args[i] if i < len(args) else '')
            if not a[2:]:
                i += 1
            r['libs'].append('-l' + name)
        elif a == '-framework' and i < len(args):
            r['libs'].append('-framework ' + args[i])
            i += 1
        elif a.startswith('-Wl,'):
            parts = a[4:].split(',')
            j = 0
            while j < len(parts):
                p = parts[j]
                if p in ('-rpath', '--rpath', '-R') and j + 1 < len(parts):
                    r['rpath'].append(parts[j + 1])
                    j += 2
                    continue
                if p.startswith(('-rpath=', '--rpath=')):
                    r['rpath'].append(p.split('=', 1)[1])
                elif p in ('-soname', '-h') and j + 1 < len(parts):
                    r['flags'].append(f'-Wl,{p},<soname>')
                    j += 2
                    continue
                elif p in ('-rpath-link',) and j + 1 < len(parts):
                    j += 2
                    continue
                else:
                    r['flags'].append('-Wl,' + p)
                j += 1
        elif a in ('-Xlinker',) and i < len(args):
            r['flags'].append('-Xlinker ' + args[i])
            i += 1
        elif a in NOISE:
            continue
        elif not a.startswith('-'):
            low = a.lower()
            if re.search(r'\.(o|obj)$', low):
                r['objects'].append(absolute(a, cwd, windows))
            elif re.search(r'(\.so(\.\d+)*|\.a|\.lib|\.dylib|\.tbd)$', low):
                r['libs'].append(absolute(a, cwd, windows))
            else:
                r['flags'].append(a)
        elif re.match(r'^-O[0-3s]?$|^-g|^-std=|^-W[^l]|^-f(PIC|PIE|pic|pie)$|^-[DU]', a):
            continue  # compile options repeated on the link line by CMake/qmake
        else:
            r['flags'].append(a)
    return r
