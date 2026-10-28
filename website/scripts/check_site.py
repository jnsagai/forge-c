"""Validate built pages, fragments, project base paths, and publication boundaries."""
from __future__ import annotations

from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1] / 'dist'
BASE = os.environ.get('BASE_PATH', '/forge-c/')
ORIGIN = os.environ.get('SITE_URL', 'https://jnsagai.github.io')


class Page(HTMLParser):
    def __init__(self, text: str):
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.urls = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.add(attrs['id'])
        for key in ('href', 'src', 'action'):
            if attrs.get(key):
                self.urls.append((f'{tag}:canonical' if tag == 'link' and attrs.get('rel') == 'canonical' else tag, attrs[key]))


def resolve_path(url: str, source: Path, root: Path = ROOT, base: str = BASE) -> tuple[Path, str] | None:
    parts = urlsplit(url)
    if parts.scheme or parts.netloc:
        if parts.scheme not in ('http', 'https') or parts.netloc != urlsplit(ORIGIN).netloc:
            return None
    path = unquote(parts.path)
    if not path:
        return source, unquote(parts.fragment)
    if path.startswith('/'):
        if not path.startswith(base):
            raise ValueError(f'URL escapes hosting base {base}: {url}')
        target = root / path[len(base):]
    else:
        target = source.parent / path
    target = target.resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f'URL escapes build directory: {url}')
    if target.is_dir() or path.endswith('/'):
        target /= 'index.html'
    return target, unquote(parts.fragment)


def check() -> dict:
    pages = {}
    issues = []
    for path in sorted(ROOT.rglob('*.html')):
        text = path.read_text()
        pages[path.resolve()] = Page(text)
        if re.search(r'/(?:home/jefferson|media/jefferson|srv/forge-c)/|master\.local|codex-preview', text):
            issues.append(f'{path.relative_to(ROOT)}: private host path or temporary metadata')
    if len(pages) < 21:
        issues.append(f'Expected at least 21 HTML pages, got {len(pages)}')
    checked = 0
    for source, page in pages.items():
        for tag, url in page.urls:
            try:
                resolved = resolve_path(url, source)
                if resolved is None:
                    continue
                target, fragment = resolved
                checked += 1
                if source.name == '404.html' and tag == 'link:canonical' and target == ROOT.resolve() / '404/index.html':
                    continue
                if not target.is_file():
                    issues.append(f'{source.relative_to(ROOT)}: missing {url}')
                elif fragment and target in pages and fragment not in pages[target].ids:
                    issues.append(f'{source.relative_to(ROOT)}: missing fragment {url}')
            except ValueError as exc:
                issues.append(f'{source.relative_to(ROOT)}: {exc}')
    manifest_path = ROOT / 'publication-manifest.json'
    if not manifest_path.is_file():
        issues.append('Missing publication manifest')
    else:
        manifest = json.loads(manifest_path.read_text())
        if manifest.get('licensed_inputs_read') is not False or manifest.get('factory_executed') is not False:
            issues.append('Invalid publication boundaries')
        if len(manifest.get('source_revision', '')) != 40:
            issues.append('Invalid source revision')
    for required in ('pagefind/pagefind.js', 'pagefind/pagefind-ui.js', 'pagefind/pagefind-ui.css', 'favicon.svg'):
        if not (ROOT / required).is_file():
            issues.append(f'Missing required asset {required}')
    if issues:
        raise SystemExit('\n'.join(issues))
    result = {'pages': len(pages), 'internal_urls': checked, 'base': BASE, 'result': 'PASS'}
    print(json.dumps(result))
    return result


if __name__ == '__main__':
    check()
