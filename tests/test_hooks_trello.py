"""Pruebas de plugins/desa/hooks: el recordatorio de la sesión de Trello. Uso: python3 -m unittest discover -s tests"""

import json
import os
import pathlib
import subprocess
import tempfile
import unittest

HOOKS = pathlib.Path(__file__).resolve().parents[1] / 'plugins' / 'desa' / 'hooks'
SCRIPT = HOOKS / 'trello-recordatorio.sh'
REFERENCIA = HOOKS.parent / 'references' / 'trello.md'


def repo(base, remote=None):
    path = pathlib.Path(base, 'repo')
    path.mkdir()
    subprocess.run(['git', 'init', '-q', str(path)], check=True)
    if remote:
        subprocess.run(['git', '-C', str(path), 'remote', 'add', 'origin', remote], check=True)
    return path


class Recordatorio(unittest.TestCase):
    def ejecutar(self, remote, modo):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, CLAUDE_PROJECT_DIR=str(repo(tmp, remote)))
            return subprocess.run(['bash', str(SCRIPT), modo], capture_output=True, text=True, env=env, check=True).stdout

    def contexto(self, salida, evento):
        datos = json.loads(salida)['hookSpecificOutput']
        self.assertEqual(datos['hookEventName'], evento)
        return datos['additionalContext']

    def test_habla_en_los_repos_de_desa(self):
        remotes = [
            'https://github.com/alexbonillax/grupodesa-front',
            'https://github.com/alexbonillax/grupodesa-backend.git',
            'git@github.com:alexbonillax/desa-dbt.git',
            'https://github.com/alexbonillax/desa-mcp-server/',
        ]
        for remote in remotes:
            with self.subTest(remote=remote):
                inicio = self.contexto(self.ejecutar(remote, 'inicio'), 'SessionStart')
                self.assertIn(str(REFERENCIA), inicio)
                self.assertIn('«Sesión › Vincular»', inicio)
                commit = self.contexto(self.ejecutar(remote, 'commit'), 'PostToolUse')
                self.assertIn(str(REFERENCIA), commit)
                self.assertIn('«Sesión › Cerrar»', commit)

    def test_calla_fuera_de_desa(self):
        for remote in ['https://github.com/alexbonillax/refy-api.git', 'git@github.com:EnGaMa98/gymric_backend.git',
                       'https://github.com/x/mi-grupodesa-fork', None]:
            with self.subTest(remote=remote):
                self.assertEqual(self.ejecutar(remote, 'inicio'), '')
                self.assertEqual(self.ejecutar(remote, 'commit'), '')

    def test_fuera_de_un_repo_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, CLAUDE_PROJECT_DIR=tmp)
            salida = subprocess.run(['bash', str(SCRIPT), 'inicio'], capture_output=True, text=True, env=env, check=True)
            self.assertEqual(salida.stdout, '')

    def test_modo_desconocido(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, CLAUDE_PROJECT_DIR=str(repo(tmp, 'https://github.com/x/grupodesa-front')))
            salida = subprocess.run(['bash', str(SCRIPT), 'otro'], capture_output=True, text=True, env=env)
            self.assertEqual(salida.returncode, 64)
            self.assertEqual(salida.stdout, '')


class HooksJson(unittest.TestCase):
    def test_eventos_y_script(self):
        hooks = json.loads((HOOKS / 'hooks.json').read_text(encoding='utf-8'))['hooks']
        inicio = hooks['SessionStart'][0]['hooks'][0]['command']
        self.assertTrue(inicio.endswith('trello-recordatorio.sh" inicio'))
        bash = next(grupo for grupo in hooks['PostToolUse'] if grupo['matcher'] == 'Bash')
        self.assertEqual({hook['if'] for hook in bash['hooks']}, {'Bash(git commit:*)', 'Bash(git -C * commit *)'})
        for hook in bash['hooks']:
            self.assertTrue(hook['command'].endswith('trello-recordatorio.sh" commit'))
        self.assertTrue(SCRIPT.exists())

    def test_la_referencia_tiene_las_secciones_que_cita(self):
        texto = REFERENCIA.read_text(encoding='utf-8')
        for seccion in ('## Sesión', '### Vincular', '### Cerrar'):
            self.assertIn(seccion, texto)


if __name__ == '__main__':
    unittest.main()
