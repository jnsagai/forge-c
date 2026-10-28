"""Generate public structural references from a bounded set of tracked source files.

No production imports, execution of CLI help, runtime config values, or input manual reads.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parents[2]
WEBSITE = ROOT / 'website'
OUTPUT = WEBSITE / 'src/content/docs/docs/reference/generated'
SCHEMAS = [
    'specs/002-self-healing-factory/contracts/agent-output.schema.json',
    'specs/002-self-healing-factory/contracts/tool-result.schema.json',
    'specs/003-manufacturing-kpis/contracts/kpi-snapshot.schema.json',
    'specs/004-continuous-reliability-engineering/contracts/capa-record.schema.json',
    'specs/005-autonomous-factory-operations/contracts/work-order.schema.json',
    'specs/006-enhanced-ai-software-assurance/contracts/verification-run.schema.json',
    'specs/006-enhanced-ai-software-assurance/contracts/safety-scope.schema.json',
    'specs/007-kpi-control-room/contracts/floor-snapshot.schema.json',
    'specs/008-brownfield-work-orders/contracts/brownfield-workorder.schema.json',
    'specs/009-peripheral-generic-iwdg/contracts/peripheral-profile.schema.json',
]
CONFIGS = {
    'config/factory/agents.yaml': 'Role permissions and required skills',
    'config/factory/mcp-registry.yaml': 'MCP services and operations',
    'config/factory/supervisor-policy.yaml': 'Health supervision and bounded recovery',
    'config/factory/trace-policy.yaml': 'Capture, privacy, and retention',
    'config/factory/token-policy.yaml': 'Agent budgets and limits',
    'config/factory/kpi-policy.yaml': 'Manufacturing KPI definitions',
    'config/factory/reliability-policy.yaml': 'Reliability and CAPA controls',
    'config/factory/afo-policy.yaml': 'Autonomous operations authority and modes',
    'config/factory/assurance-policy.yaml': 'Assurance methods and evidence policy',
}
MODULES = [
    ('workorder', ['run', 'main']),
    ('release/finalize', ['finalize', 'verify_archive', 'main']),
    ('fabro/progress', ['main']),
    ('dashboard/app', ['main']),
    ('kpi/service', ['compute_and_store']),
]


def clean(value: object) -> str:
    """Escape metadata before placing it into Markdown prose or a table."""
    return str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('|', '&#124;').replace('\n', ' ').replace('`', '&#96;')


def literal(node: ast.AST) -> object:
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return ast.unparse(node)


def command_options(source: str) -> list[dict]:
    tree = ast.parse(source)
    result = []
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    for call in ast.walk(main):
        if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute) or call.func.attr != 'add_argument':
            continue
        options = [literal(arg) for arg in call.args]
        if not options or not all(isinstance(option, str) and option.startswith('-') for option in options):
            raise ValueError('Unsupported argument declaration')
        result.append({'flags': options, **{kw.arg: literal(kw.value) for kw in call.keywords}, 'line': call.lineno})
    return sorted(result, key=lambda row: row['line'])


def example_metadata(path: Path) -> dict:
    """Extract only structural work-order fields; never follow its input paths."""
    data = json.loads(path.read_text())
    delivery = data.get('delivery', {})
    return {'name': path.parent.name, 'driver': data['driver'], 'part': data.get('target', {}).get('part_number', 'Not specified'),
            'layer': data.get('layer', 'LL+HAL (legacy)'), 'mode': delivery.get('code_mode', 'Generated'),
            'peripheral': data.get('peripheral', 'rcc (baseline)')}


def generate() -> dict:
    tracked = set(subprocess.check_output(['git', 'ls-files'], cwd=ROOT, text=True).splitlines())
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    source_url = f'https://github.com/jnsagai/forge-c/blob/{revision}/'
    inputs = {}

    def read(relative: str) -> str:
        if relative not in tracked:
            raise ValueError(f'Reference input is not tracked: {relative}')
        path = ROOT / relative
        if not path.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError(f'Reference input escapes the source tree: {relative}')
        raw = path.read_bytes()
        inputs[relative] = hashlib.sha256(raw).hexdigest()
        return raw.decode()

    def link(relative: str, label: str | None = None) -> str:
        return f'[{clean(label or relative)}]({source_url}{relative})'

    def write(slug: str, title: str, body: str) -> None:
        (OUTPUT / f'{slug}.md').write_text(f'---\ntitle: {json.dumps(title)}\neditUrl: false\n---\n\n'
            f'Generated from source revision `{revision[:12]}`. This is structural reference, not runtime verification.\n\n{body}\n')

    OUTPUT.mkdir(parents=True, exist_ok=True)
    # Replace the entire generated directory, leaving authored narrative untouched.
    for old in OUTPUT.glob('*.md'):
        old.unlink()

    path = 'factory/python/forge_factory/workorder.py'
    options = command_options(read(path))
    lines = ['## Work-order command', '', '```sh', 'python -m forge_factory.workorder --example <directory> --wo <unique-id> [options]', '```', '',
        'Flags are read from argparse declarations without executing the command. For options without help text, the description is a structural label.', '',
        '| Option | Default / requirement | Description |', '| --- | --- | --- |']
    for option in options:
        default = 'Required' if option.get('required') else str(option.get('default', False if option.get('action') == 'store_true' else 'None'))
        help_text = option.get('help', {'--example': 'Example input directory', '--wo': 'Unique work-order identifier', '--detach': 'Submit without waiting for completion'}.get(option['flags'][0], 'See source'))
        if 'choices' in option:
            help_text += f"; choices: {', '.join(option['choices'])}"
        lines.append(f"| {', '.join('`'+clean(f)+'`' for f in option['flags'])} | {clean(default)} | {clean(help_text)} |")
    lines += ['', 'Source: ' + link(path), '', '## Developer targets', '', 'These Makefile targets run on a configured development host. Some use the factory environment; they are not invoked by the website build.', '', '| Target | Source |', '| --- | --- |']
    makefile = read('Makefile')
    for target in re.findall(r'^([a-z][a-z0-9-]*):', makefile, re.M):
        lines.append(f'| `make {target}` | {link("Makefile", "Makefile")} |')
    write('commands', 'Command reference', '\n'.join(lines))

    lines = ['## Configuration files', '', 'The website lists locations and responsibilities only. It does not publish configuration values or runtime state.', '', '| Source | Responsibility |', '| --- | --- |']
    for path, label in CONFIGS.items():
        read(path)
        lines.append(f'| {link(path)} | {label} |')
    lines += ['', '## Selected schema contracts', '', 'Required top-level fields are extracted from each schema. Conditional rules, referenced definitions, and nested constraints remain authoritative in the linked JSON schema.', '']
    for path in SCHEMAS:
        schema = json.loads(read(path))
        lines += [f'### {clean(Path(path).name)}', '', link(path, 'View complete schema'), '',
            f"Required top-level fields: {', '.join('`'+clean(field)+'`' for field in schema.get('required', [])) or 'none unconditionally declared' }.", '',
            f"Declared top-level properties: {', '.join('`'+clean(field)+'`' for field in schema.get('properties', {})) or 'see composed schema'}.", '']
    write('contracts', 'Configuration and contracts', '\n'.join(lines))

    lines = ['A fresh clone contains these work-order specifications. Licensed reference inputs may be absent. Metadata below does not imply those inputs are present or that a new run will succeed.', '',
        '| Example | Driver | Layer | Mode |', '| --- | --- | --- | --- |']
    example_paths = sorted(p for p in tracked if re.fullmatch(r'examples/[^/]+/workorder\.json', p))
    if not example_paths:
        raise ValueError('No tracked work-order examples found')
    for path in example_paths:
        read(path)
        info = example_metadata(ROOT / path)
        lines.append(f"| {link(path, info['name'])} | {clean(info['driver'])} | {clean(info['layer'])} | {clean(info['mode'])} |")
    lines += ['', '## Layer dependencies', '', 'HAL orders need `--provided-from` a verified LL order. See [LL and HAL](/docs/guides/ll-and-hal/). The combined legacy RCC order is preserved as source history.', '',
        '## Licensed inputs', '', 'Only selected metadata from tracked work-order JSON is published here. The generator never reads or copies the input files referenced by those orders. Obtain applicable documents through your authorized channels.']
    write('examples', 'Example work orders', '\n'.join(lines))

    project = tomllib.loads(read('pyproject.toml'))['project']
    lines = [f"Factory package: `{project['name']}` version `{project['version']}`; Python requirement: `{project['requires-python']}`.", '',
        '## Installed command entry points', '', '| Command | Callable |', '| --- | --- |']
    for name, callable_ in project.get('scripts', {}).items():
        lines.append(f'| `{clean(name)}` | `{clean(callable_)}` |')
    lines += ['', '## Selected Python interfaces', '', 'Signatures and docstrings are extracted using Python AST. Production modules are not imported. These are selected navigation entries, not a complete API stability contract.', '']
    for module, names in MODULES:
        path = f'factory/python/forge_factory/{module}.py'
        tree = ast.parse(read(path))
        functions = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        for name in names:
            if name not in functions:
                raise ValueError(f'Missing documented interface: {module}:{name}')
            node = functions[name]
            args = ast.unparse(node.args)
            lines += [f'### {module.replace("/", ".")}.{name}', '', '```python', f'def {name}({args})', '```', '',
                clean(ast.get_docstring(node) or 'See the source implementation for behavior, prerequisites, and return values.'), '',
                f'[Source]({source_url}{path}#L{node.lineno})', '']
    write('python', 'Python entry points and interfaces', '\n'.join(lines))
    manifest = {'schema': 'forge-c/publication/1', 'source_revision': revision, 'inputs': dict(sorted(inputs.items())),
                'generated_pages': sorted(p.name for p in OUTPUT.glob('*.md')), 'factory_executed': False, 'licensed_inputs_read': False}
    (WEBSITE / 'public/publication-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest


if __name__ == '__main__':
    manifest = generate()
    print(f"Generated {len(manifest['generated_pages'])} reference pages from {len(manifest['inputs'])} tracked inputs at {manifest['source_revision'][:12]}")
