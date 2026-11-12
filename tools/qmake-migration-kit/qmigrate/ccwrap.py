#!/usr/bin/env python3
"""Compiler/linker wrapper used by `qmig capture`: records the command, then runs it.

Usage: ccwrap.py LOG_DIR KIND TOOL [ARGS...]
KIND is cc, cxx, link, ar or lib. One JSON file per invocation is written to LOG_DIR
(safe for parallel builds). Response files (@file) are recorded with their content,
because build tools often delete them right after the call. Standard library only.
"""
import json
import os
import subprocess
import sys
import time


def read_response(path):
    try:
        data = open(path, 'rb').read()
    except OSError:
        return None
    for bom, encoding in ((b'\xff\xfe', 'utf-16-le'), (b'\xfe\xff', 'utf-16-be'), (b'\xef\xbb\xbf', 'utf-8')):
        if data.startswith(bom):
            return data[len(bom):].decode(encoding, 'replace')
    return data.decode('utf-8', 'replace')


def main():
    if len(sys.argv) < 4:
        sys.stderr.write(__doc__)
        return 2
    log_dir, kind, argv = sys.argv[1], sys.argv[2], sys.argv[3:]
    cwd = os.getcwd()
    responses = {}
    for arg in argv[1:]:
        if arg.startswith('@') and len(arg) > 1:
            path = arg[1:] if os.path.isabs(arg[1:]) else os.path.join(cwd, arg[1:])
            content = read_response(path)
            if content is not None:
                responses[arg] = content
    start = time.time()
    try:
        rc = subprocess.call(argv)
    except OSError as error:
        sys.stderr.write(f'ccwrap: cannot run {argv[0]}: {error}\n')
        rc = 127
    record = dict(kind=kind, cwd=cwd, argv=argv, responses=responses, rc=rc,
                  seconds=round(time.time() - start, 3))
    try:
        os.makedirs(log_dir, exist_ok=True)
        name = os.path.join(log_dir, f'{time.time_ns()}-{os.getpid()}')
        with open(name + '.tmp', 'w', encoding='utf-8') as fh:
            json.dump(record, fh)
        os.replace(name + '.tmp', name + '.json')
    except OSError as error:
        sys.stderr.write(f'ccwrap: cannot write log: {error}\n')
    return rc


if __name__ == '__main__':
    sys.exit(main())
