"""Host-only C ABI for GoogleTest of delivered CMSIS inline code.

Vendor headers remain unchanged and their real bodies compile as C. C++ sees
declarations derived from those headers, with the same constants and types. The
generated C translation unit forwards only the resolved work-order scope; an
unallocated function has no generated external implementation.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..common import sha256_file
from . import DELIVERY_DIR, cmsis, delivered_paths, manifest_of
from . import scope as S


def generate(ws: Path, output: Path) -> tuple[Path, Path] | None:
    manifest = manifest_of(ws)
    if not cmsis.gtest_linkage(manifest) or not cmsis.is_cmsis(ws):
        return None
    headers = [ws / p for p in delivered_paths(manifest) if p.endswith('.h')]
    resolved = json.loads((ws / DELIVERY_DIR / 'scope.json').read_text())
    selected = [r['name'] for r in resolved.get('functions', [])]
    if not selected:
        raise ValueError('CMSIS_GTEST_SCOPE_INVALID')
    return _generate(ws, output, headers, selected, cmsis.GTEST_LINKAGE)


def _generate(ws: Path, output: Path, headers: list[Path], selected: list[str], linkage: str):
    if (any(not isinstance(n, str) or not re.fullmatch(S.IDENT, n) for n in selected)
            or len(selected) != len(set(selected)) or not headers):
        raise ValueError('CMSIS_GTEST_SCOPE_INVALID')
    if len({p.name for p in headers}) != len(headers):
        raise ValueError('CMSIS_GTEST_HEADER_NAME_COLLISION')
    signatures = {}
    destination = output / 'cmsis-c-abi'
    destination.mkdir(parents=True, exist_ok=True)
    sources = []
    for header in headers:
        raw = header.read_text()
        code = S._blank_directives(S.strip_comments(raw))
        edits, aliases = [], []
        for match in S.FUNC_HEAD.finditer(code):
            if not re.search(r'inline|INLINE', match.group('quals')):
                continue
            name = match.group('name')
            qualifiers = re.sub(r'\b(?:static|inline|__inline|__STATIC_INLINE|__STATIC_FORCEINLINE|__INLINE|extern)\b',
                                '', match.group('quals'))
            returns = ' '.join((qualifiers + match.group('ret')).split())
            params = ' '.join(match.group('params').split()) or 'void'
            args = []
            if name in selected and params != 'void':
                for parameter in params.split(','):
                    identifier = re.search(r'([A-Za-z_]\w*)\s*$', parameter)
                    if not identifier or '(' in parameter or '[' in parameter:
                        raise ValueError('CMSIS_GTEST_SIGNATURE_UNSUPPORTED:' + name)
                    args.append(identifier[1])
            if name in signatures:
                raise ValueError('CMSIS_GTEST_SIGNATURE_AMBIGUOUS:' + name)
            signatures[name] = (returns, params, args)
            aliases.append(f'#define {name} forge_cmsis_cabi_{name}')
            end = S._balanced(code, match.end() - 1, '{', '}')
            if end < match.end():
                raise ValueError('CMSIS_GTEST_HEADER_UNBALANCED:' + name)
            edits.append((match.start(), end, f'extern {returns} forge_cmsis_cabi_{name}({params});'))
        shadow = raw
        for start, end, declaration in reversed(edits):
            shadow = shadow[:start] + declaration + shadow[end:]
        target = destination / header.name
        target.write_text('/* GENERATED host C-ABI declarations; vendor function bodies execute in C. */\n'
                          + shadow + '\n' + '\n'.join(aliases) + '\n')
        sources.append({'path': str(header.relative_to(ws)), 'sha256': sha256_file(header),
                        'declarations_sha256': sha256_file(target)})
    missing = sorted(set(selected) - signatures.keys())
    if missing:
        raise ValueError('CMSIS_GTEST_SCOPED_SIGNATURE_MISSING:' + ','.join(missing))
    lines = ['/* GENERATED host-only C forwarding unit. No driver logic is replaced. */',
             '#include "forge_host_device.h"']
    lines += [f'#include "{header.as_posix()}"' for header in headers]
    for name in selected:
        returns, params, args = signatures[name]
        symbol = 'forge_cmsis_cabi_' + name
        lines += [f'{returns} {symbol}({params});',
                  f'{returns} {symbol}({params}) {{ ' + ('' if returns == 'void' else 'return ')
                  + f'{name}({", ".join(args)}); }}']
    source = output / 'forge_cmsis_ll_abi.c'
    source.write_text('\n'.join(lines) + '\n')
    (destination / 'binding.json').write_text(json.dumps({
        'schema': 'forge-c/cmsis-host-c-abi/1', 'linkage': linkage,
        'source_headers': sources, 'resolved_scope': selected,
        'exported_symbols': ['forge_cmsis_cabi_' + name for name in selected],
        'forwarding_unit_sha256': sha256_file(source), 'environment': 'HOST_ONLY',
        'target_or_hil_claim': False}, indent=2) + '\n')
    return destination, source
