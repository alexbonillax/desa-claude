"""Pruebas del frontmatter de plugins/desa/commands/*.md. Uso: python3 -m unittest discover -s tests

`claude plugin validate --strict` no detecta un frontmatter que no es YAML válido. Si no parsea,
Claude Code pierde allowed-tools, disable-model-invocation y hooks sin avisar.
"""

import json
import pathlib
import re
import subprocess
import tempfile
import unittest

try:
    import yaml
except ImportError:  # sin PyYAML quedan las comprobaciones de texto
    yaml = None

COMMANDS = pathlib.Path(__file__).resolve().parents[1] / 'plugins' / 'desa' / 'commands'


def frontmatter(path):
    text = path.read_text(encoding='utf-8')
    match = re.match(r'---\n(.*?)\n---\n', text, re.S)
    if not match:
        raise AssertionError(f'{path.name}: sin frontmatter')
    return match.group(1)


class Frontmatter(unittest.TestCase):
    def test_escalares_planos_sin_dos_puntos(self):
        # En YAML, ": " o " #" dentro de un escalar sin comillas lo rompen.
        for path in sorted(COMMANDS.glob('*.md')):
            for line in frontmatter(path).splitlines():
                m = re.match(r'([\w-]+): (.+)$', line)
                if not m or m.group(2)[0] in '"\'[{>|':
                    continue
                with self.subTest(fichero=path.name, clave=m.group(1)):
                    self.assertNotIn(': ', m.group(2))
                    self.assertNotIn(' #', m.group(2))

    @unittest.skipIf(yaml is None, 'sin PyYAML')
    def test_parsea_como_yaml(self):
        for path in sorted(COMMANDS.glob('*.md')):
            with self.subTest(fichero=path.name):
                data = yaml.safe_load(frontmatter(path))
                self.assertIsInstance(data, dict)
                self.assertLessEqual(len(data['description']), 1536)


SHELLS = [sh for sh in ('/bin/sh', '/bin/bash', '/bin/zsh', '/usr/bin/zsh') if pathlib.Path(sh).exists()]


class HookDePlan(unittest.TestCase):
    def comando(self, matcher):
        fm = frontmatter(COMMANDS / 'plan.md')
        if yaml is not None:
            hooks = {h['matcher']: h['hooks'][0]['command'] for h in yaml.safe_load(fm)['hooks']['PreToolUse']}
            return hooks[matcher]
        # Sin PyYAML: el bloque que sigue a `- matcher: "<matcher>"`, en forma `>-` (una línea) o `|-` (varias).
        bloque = fm.split(f'- matcher: "{matcher}"', 1)[1]
        m = re.search(r'command: (>-|\|-)\n((?:[ ]{12}.*\n?)+)', bloque)
        lineas = [l[12:] for l in m.group(2).splitlines()]
        return ' '.join(lineas) if m.group(1) == '>-' else '\n'.join(lineas)

    def decision(self, salida):
        decision = json.loads(salida)['hookSpecificOutput']
        self.assertEqual(decision['hookEventName'], 'PreToolUse')
        return decision['permissionDecision']

    def test_workflow_pide_confirmacion(self):
        salida = subprocess.run(['/bin/sh', '-c', self.comando('Workflow')], capture_output=True, text=True, check=True).stdout
        self.assertEqual(self.decision(salida), 'ask')

    def test_agent_pide_confirmacion_desde_el_cuarto(self):
        for shell in SHELLS:
            with self.subTest(shell=shell), tempfile.TemporaryDirectory() as tmp:
                entrada = json.dumps({'session_id': 'abc-123', 'tool_name': 'Agent', 'tool_input': {'prompt': 'x'}})
                salidas = [
                    subprocess.run([shell, '-c', self.comando('Agent')], input=entrada, capture_output=True,
                                   text=True, check=True, env={'PATH': '/usr/bin:/bin', 'TMPDIR': tmp}).stdout
                    for _ in range(5)
                ]
                self.assertEqual(salidas[:3], ['', '', ''])
                self.assertEqual([self.decision(s) for s in salidas[3:]], ['ask', 'ask'])
                # Otra sesión lleva su propia cuenta.
                otra = json.dumps({'session_id': 'otra', 'tool_name': 'Agent'})
                salida = subprocess.run([shell, '-c', self.comando('Agent')], input=otra, capture_output=True,
                                        text=True, check=True, env={'PATH': '/usr/bin:/bin', 'TMPDIR': tmp}).stdout
                self.assertEqual(salida, '')


if __name__ == '__main__':
    unittest.main()
