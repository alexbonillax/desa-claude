"""Pruebas de plugins/desa/scripts/terms.py. Uso: python3 -m unittest discover -s tests"""

import contextlib
import io
import json
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'plugins' / 'desa' / 'scripts'))
import terms  # noqa: E402

HAS_PHP = shutil.which('php') is not None
GIT_VARS = ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES',
            'GIT_COMMON_DIR', 'GIT_PREFIX', 'GIT_NAMESPACE')


def term(tid, ns, code, **value):
    return {'id': tid, 'fields': {'namespace': ns, 'code': code, 'value': value}}


class FakeApi:
    """Sustituye desa_api.request: responde a /locales y /terms con datos en memoria."""

    def __init__(self, locales, terms_by_ns, fail_page=None):
        self.locales, self.terms, self.fail_page = locales, terms_by_ns, fail_page
        self.calls = []

    def __call__(self, method, path, params=None, body=None):
        params = dict(params or [])
        self.calls.append((method, path, params, body))
        if path == '/locales':
            return 200, {'data': [{'fields': {'code': c}} for c in self.locales]}
        if method == 'GET' and path == '/terms' and 'filter[code]' in params:
            for t in self.terms.get(params['filter[namespace]'], []):
                if t['fields']['code'] == params['filter[code]']:
                    return 200, {'data': t}
            return 404, {'message': 'Not Found'}
        if method == 'GET' and path == '/terms' and 'filter[search]' in params:
            items = [t for ts in self.terms.values() for t in ts]
            return 200, {'data': items, 'meta': {'page': 1, 'total': len(items), 'has_more_pages': False}}
        if method == 'GET' and path == '/terms':
            page = int(params.get('page', 1))
            if self.fail_page == page:
                return 401, {'message': 'Unauthenticated.'}
            items = self.terms.get(params.get('filter[namespace]'), [])
            chunk = items[(page - 1) * 2: page * 2]
            return 200, {'data': chunk, 'meta': {'has_more_pages': page * 2 < len(items)}}
        if method == 'POST':
            return 201, {'data': body}
        if method == 'DELETE':
            return 200, None
        return 500, None

    def methods(self):
        return [(c[0], c[1]) for c in self.calls if c[0] != 'GET']


class Project(unittest.TestCase):
    def setUp(self):
        self.env = dict(os.environ)
        self.tmp = tempfile.TemporaryDirectory()
        self.top = pathlib.Path(self.tmp.name).resolve()
        for var in GIT_VARS:
            os.environ.pop(var, None)
        os.environ.update({'GIT_CEILING_DIRECTORIES': str(self.top.parent), 'GIT_CONFIG_GLOBAL': '/dev/null',
                           'GIT_CONFIG_NOSYSTEM': '1'})
        subprocess.run(['git', 'init', '-q', str(self.top)], check=True)
        self.cwd = os.getcwd()
        os.chdir(self.top)
        self.real_request = terms.desa_api.request

    def tearDown(self):
        terms.desa_api.request = self.real_request
        os.chdir(self.cwd)
        os.environ.clear()
        os.environ.update(self.env)
        for p in self.top.rglob('*'):
            if p.is_dir():
                p.chmod(0o755)
        self.tmp.cleanup()

    def write(self, rel, text):
        p = self.top / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')
        return p

    def run_main(self, argv, api=None, stdin=None):
        if api:
            terms.desa_api.request = api
        out, err = io.StringIO(), io.StringIO()
        old_stdin = sys.stdin
        if stdin is not None:
            sys.stdin = io.StringIO(stdin)
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = terms.main(argv)
        finally:
            sys.stdin = old_stdin
        return code, out.getvalue(), err.getvalue()


class FormatTest(unittest.TestCase):
    def test_php_str_los_tres_casos_de_p0_2(self):
        self.assertEqual(terms.php_str('Total en $currency'), '"Total en \\$currency"')
        self.assertEqual(terms.php_str("{${print('X')}}"), '"{\\${print(\'X\')}}"')
        self.assertEqual(terms.php_str('C:\\ruta\\"q"'), '"C:\\\\ruta\\\\\\"q\\""')

    @unittest.skipUnless(HAS_PHP, 'php no disponible')
    def test_php_str_ida_y_vuelta_en_php(self):
        values = {'a': 'Total en $currency', 'b': "{${print('X')}}", 'c': 'C:\\ruta\\"q"',
                  'd': "l'élément", 'e': '{$x} y ${y}', 'f': 'línea\nnueva', 'g': 'barra final\\'}
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d, 'app.php')
            p.write_text(terms.gen_php(values), encoding='utf-8')
            out = subprocess.run(['php', '-d', 'error_reporting=-1', '-r',
                                  'echo json_encode(require $argv[1], JSON_UNESCAPED_UNICODE);', str(p)],
                                 capture_output=True, text=True)
            self.assertEqual(out.stderr, '')
            self.assertEqual(json.loads(out.stdout), values)
            self.assertEqual(terms.parse_php(p.read_text(encoding='utf-8')), values)

    def test_gen_php_alineado_y_ordenado(self):
        self.assertEqual(terms.gen_php({'b.largo': 'B', 'a': 'A'}),
                         '<?php\n\nreturn array(\n    "a"       => "A",\n    "b.largo" => "B",\n);\n')

    def test_gen_json_utf8_ordenado(self):
        self.assertEqual(terms.gen_json({'b': 'Configuración', 'a': 'x'}),
                         '{\n  "a": "x",\n  "b": "Configuración"\n}\n')

    def test_parse_php_formatos_planos(self):
        legacy = "<?php\n// comentario\nreturn [\n    'a' => 'l\\'élément',\n    \"b\" => \"tab\\tfin \\x41\\101\",  /* x */\n    'c' => \"precio $5\",\n];\n"
        self.assertEqual(terms.parse_php(legacy), {'a': "l'élément", 'b': 'tab\tfin AA', 'c': 'precio $5'})

    def test_parse_php_no_ejecuta_nada(self):
        for bad in ('<?php return array("a" => "$x");', '<?php return array("a" => "{$x}");',
                    '<?php file_put_contents("x", 1); return array();', '<?php return array("a" => strtoupper("b"));',
                    '<?php return array("a" => array("b" => "c"));', '<?php return array(1 => "x");'):
            with self.assertRaises(ValueError, msg=bad):
                terms.parse_php(bad)

    def test_clean_value(self):
        self.assertEqual(terms.clean_value([]), {})
        self.assertEqual(terms.clean_value(None), {})
        self.assertEqual(terms.clean_value({'es': 'A', 'fr': None, 'pt': '  ', 'it': 3}), {'es': 'A'})


class ProjectTest(Project):
    def test_frontend(self):
        self.write('packages/i18n/src/locales/es/translations.json', '{}\n')
        code, out, _ = self.run_main(['project'])
        self.assertIn('PROYECTO=frontend', out)
        self.assertIn('NAMESPACES=app', out)

    def test_backend_excluye_ficheros_de_laravel_y_admite_lang(self):
        for f in ('es/app.php', 'es/auth.php', 'es/validation.php', 'fr/notifications.php'):
            self.write(f'lang/{f}', '<?php return [];')
        code, out, _ = self.run_main(['project'])
        self.assertIn('PROYECTO=backend', out)
        self.assertIn('RAIZ=lang', out)
        self.assertIn('NAMESPACES=app notifications', out)

    def test_sin_proyecto(self):
        self.assertIn('PROYECTO=no-project', self.run_main(['project'])[1])

    def test_apply_solo_en_los_que_escriben(self):
        self.assertEqual(self.run_main(['find', '--ns', 'app', '--code', 'x', '--apply'])[0], 1)


class SyncFrontendTest(Project):
    def setUp(self):
        super().setUp()
        self.es = self.write('packages/i18n/src/locales/es/translations.json',
                             terms.gen_json({'a.uno': 'Uno', 'b.viejo': 'Viejo', 'c.cambia': 'Antes'}))
        self.api = FakeApi(['es', 'fr'], {'app': [
            term(1, 'app', 'a.uno', es='Uno', fr='Un'),
            term(2, 'app', 'c.cambia', es='Después'),
            term(3, 'app', 'd.nuevo', es='Nuevo', fr='Nouveau'),
        ]})

    def test_dry_run_no_escribe_y_cuenta(self):
        before = self.es.read_text()
        code, out, err = self.run_main(['sync'], self.api)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.es.read_text(), before)
        self.assertFalse((self.top / 'packages/i18n/src/locales/fr').exists())
        self.assertIn('packages/i18n/src/locales/es/translations.json: +1 ~1 -1 · bajas: b.viejo', out)
        self.assertIn('packages/i18n/src/locales/fr/translations.json: nuevo +2 ~0 -0', out)
        self.assertIn('BAJAS=1', out)
        self.assertIn('IDIOMAS_NUEVOS=fr', out)
        self.assertIn('MODO=dry-run', out)

    def test_apply_escribe_con_el_formato_del_proyecto(self):
        code, out, err = self.run_main(['sync', '--apply'], self.api)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.es.read_text(),
                         terms.gen_json({'a.uno': 'Uno', 'c.cambia': 'Después', 'd.nuevo': 'Nuevo'}))
        fr = self.top / 'packages/i18n/src/locales/fr/translations.json'
        self.assertEqual(json.loads(fr.read_text()), {'a.uno': 'Un', 'd.nuevo': 'Nouveau'})
        self.assertIn('ESCRITOS=2', out)

    def test_error_en_la_pagina_2_aborta_sin_escribir(self):
        self.api.fail_page = 2
        before = self.es.read_text()
        code, out, err = self.run_main(['sync', '--apply'], self.api)
        self.assertEqual(code, 1)
        self.assertIn('HTTP 401', err)
        self.assertEqual(self.es.read_text(), before)
        self.assertFalse((self.top / 'packages/i18n/src/locales/fr').exists())

    def test_sin_cambios(self):
        api = FakeApi(['es'], {'app': [term(1, 'app', k, es=v) for k, v in
                                       {'a.uno': 'Uno', 'b.viejo': 'Viejo', 'c.cambia': 'Antes'}.items()]})
        self.assertIn('SIN_CAMBIOS', self.run_main(['sync', '--apply'], api)[1])

    def test_avisa_de_cambios_sin_commitear(self):
        code, out, _ = self.run_main(['sync'], self.api)
        self.assertIn('CAMBIOS_SIN_COMMITEAR=packages/i18n/src/locales/es/translations.json', out)

    def test_include_ns_en_frontend_no_machaca_el_fichero(self):
        before = self.es.read_text()
        code, _, err = self.run_main(['sync', '--include-ns', 'export', '--apply'], self.api)
        self.assertEqual(code, 1)
        self.assertIn('solo existe el namespace app', err)
        self.assertEqual(self.es.read_text(), before)

    def test_obsoleto_no_se_borra(self):
        self.write('packages/i18n/src/locales/nl/translations.json', terms.gen_json({'x': 'y'}))
        api = FakeApi(['es', 'nl'], {'app': [term(1, 'app', 'a.uno', es='Uno')]})
        code, out, _ = self.run_main(['sync', '--apply'], api)
        self.assertIn('OBSOLETO=packages/i18n/src/locales/nl/translations.json', out)
        self.assertTrue((self.top / 'packages/i18n/src/locales/nl/translations.json').exists())

    def test_valores_vacios_nulos_o_lista(self):
        api = FakeApi(['es', 'fr'], {'app': [term(1, 'app', 'a.uno', es='Uno', fr=None),
                                             {'id': 2, 'fields': {'namespace': 'app', 'code': 'b.x', 'value': []}}]})
        code, out, err = self.run_main(['sync', '--apply'], api)
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(self.es.read_text()), {'a.uno': 'Uno'})
        self.assertFalse((self.top / 'packages/i18n/src/locales/fr').exists())

    def test_idioma_de_la_api_con_ruta_rara(self):
        api = FakeApi(['es', '../../x'], {'app': [term(1, 'app', 'a.uno', es='Uno')]})
        code, _, err = self.run_main(['sync', '--apply'], api)
        self.assertEqual(code, 1)
        self.assertIn('código de idioma no válido', err)
        self.assertFalse((self.top / 'x').exists())


class SyncBackendTest(Project):
    def setUp(self):
        super().setUp()
        self.write('artisan', '')
        self.app = self.write('resources/lang/es/app.php', terms.gen_php({'a': 'Hola "$nombre"'}))
        self.write('resources/lang/es/auth.php', "<?php return ['failed' => 'x'];")
        self.write('resources/lang/es/propio.php', terms.gen_php({'z': 'solo local'}))

    def test_solo_toca_namespaces_con_terms_y_respeta_laravel(self):
        api = FakeApi(['es'], {'app': [term(1, 'app', 'a', es='Hola "$nombre"'), term(2, 'app', 'b', es='{$x}')],
                               'export': [term(3, 'export', 'e', es='E')]})
        code, out, err = self.run_main(['sync', '--apply'], api)
        self.assertEqual(code, 0, err)
        self.assertIn('SIN_TERMS_EN_API=propio', out)
        self.assertIn('SOLO_EN_API=export (1 terms)', out)
        self.assertEqual(terms.load_php(self.app), {'a': 'Hola "$nombre"', 'b': '{$x}'})
        self.assertFalse((self.top / 'resources/lang/es/export.php').exists())
        consultados = [c[2].get('filter[namespace]') for c in api.calls if c[1] == '/terms']
        self.assertNotIn('auth', consultados)
        self.assertIn('propio', consultados)

    def test_namespace_ajeno_no_se_sustituye(self):
        api = FakeApi(['es'], {'propio': [term(9, 'propio', 'otra.cosa', es='Otra')]})
        before = (self.top / 'resources/lang/es/propio.php').read_text()
        code, out, _ = self.run_main(['sync', '--apply'], api)
        self.assertIn('NAMESPACE_AJENO=propio (1 claves locales, ninguna en la API)', out)
        self.assertEqual((self.top / 'resources/lang/es/propio.php').read_text(), before)

    def test_el_dry_run_no_ejecuta_php_del_repo(self):
        testigo = self.top / 'EJECUTADO'
        self.write('resources/lang/es/app.php', f"<?php file_put_contents('{testigo}', 1); return array(\"a\" => \"A\");\n")
        api = FakeApi(['es'], {'app': [term(1, 'app', 'a', es='A')]})
        code, _, err = self.run_main(['sync'], api)
        self.assertEqual(code, 1)
        self.assertIn('--allow-php', err)
        self.assertFalse(testigo.exists())

    def test_upsert_de_un_fichero_de_laravel(self):
        api = FakeApi(['es'], {})
        code, _, err = self.run_main(['upsert', '--ns', 'auth', '--code', 'x', '--values', '-', '--apply'], api, stdin='{"es": "X"}')
        self.assertEqual(code, 1)
        self.assertIn('propio de Laravel', err)
        self.assertEqual(api.methods(), [])

    def test_upsert_de_un_namespace_que_no_existe_en_local(self):
        api = FakeApi(['es'], {})
        code, out, _ = self.run_main(['upsert', '--ns', 'notifications', '--code', 'a.b', '--values', '-', '--apply'],
                                     api, stdin='{"es": "X"}')
        self.assertEqual(code, 0)
        self.assertIn('no existe en local', out)
        self.assertFalse((self.top / 'resources/lang/es/notifications.php').exists())


class UpsertDeleteTest(Project):
    def setUp(self):
        super().setUp()
        self.es = self.write('packages/i18n/src/locales/es/translations.json', terms.gen_json({'global.save': 'Guardar'}))
        self.api = FakeApi(['es', 'pt'], {'app': [term(7, 'app', 'global.save', es='Guardar')]})

    def test_upsert_dry_run_enseña_actual_y_nuevo_sin_escribir(self):
        code, out, _ = self.run_main(['upsert', '--ns', 'app', '--code', 'global.save', '--values', '-'],
                                     self.api, stdin='{"es": "Guardar cambios", "pt": "Guardar"}')
        self.assertEqual(code, 0)
        self.assertIn('actualizar id 7', out)
        self.assertIn('es: "Guardar" → "Guardar cambios"  [sobrescribe]', out)
        self.assertIn('pt: null → "Guardar"  [nuevo]', out)
        self.assertEqual(self.api.methods(), [])

    def test_upsert_apply_fusiona_y_actualiza_ficheros(self):
        code, out, err = self.run_main(['upsert', '--ns', 'app', '--code', 'global.save', '--values', '-', '--apply'],
                                       self.api, stdin='{"pt": "Guardar"}')
        self.assertEqual(code, 0, err)
        post = [c for c in self.api.calls if c[0] == 'POST'][0]
        self.assertEqual(post[1], '/terms/7')
        self.assertEqual(post[3]['fields']['value'], {'es': 'Guardar', 'pt': 'Guardar'})
        pt = self.top / 'packages/i18n/src/locales/pt/translations.json'
        self.assertEqual(json.loads(pt.read_text()), {'global.save': 'Guardar'})

    def test_upsert_avisa_de_idiomas_sin_traduccion(self):
        code, out, _ = self.run_main(['upsert', '--ns', 'app', '--code', 'x.nuevo', '--values', '-'],
                                     self.api, stdin='{"es": "Nuevo"}')
        self.assertIn('SIN_TRADUCCION=pt', out)

    def test_upsert_crea_si_no_existe(self):
        self.run_main(['upsert', '--ns', 'app', '--code', 'x.nuevo', '--values', '-', '--apply'],
                      self.api, stdin='{"es": "Nuevo"}')
        self.assertEqual(self.api.methods(), [('POST', '/terms/new')])

    def test_upsert_rechaza_cadenas_vacias(self):
        code, _, err = self.run_main(['upsert', '--ns', 'app', '--code', 'x', '--values', '-', '--apply'],
                                     self.api, stdin='{"es": ""}')
        self.assertEqual(code, 1)
        self.assertIn('cadenas vacías', err)
        self.assertEqual(self.api.methods(), [])

    def test_upsert_rechaza_idiomas_que_no_estan_en_locales(self):
        code, _, err = self.run_main(['upsert', '--ns', 'app', '--code', 'x', '--values', '-', '--apply'],
                                     self.api, stdin='{"pt-BR": "Salvar"}')
        self.assertEqual(code, 1)
        self.assertIn('no están en /locales', err)
        self.assertEqual(self.api.methods(), [])

    def test_upsert_ignora_idiomas_raros_del_term(self):
        api = FakeApi(['es'], {'app': [term(7, 'app', 'global.save', es='Guardar', **{'../../bootstrap': 'x'})]})
        code, out, err = self.run_main(['upsert', '--ns', 'app', '--code', 'global.save', '--values', '-', '--apply'],
                                       api, stdin='{"es": "Guardar ya"}')
        self.assertEqual(code, 0, err)
        self.assertIn('se ignoran: ../../bootstrap', out)
        self.assertFalse((self.top / 'packages/i18n/bootstrap').exists())

    def test_upsert_no_escribe_en_la_api_si_lo_local_falla(self):
        self.write('packages/i18n/src/locales/pt/translations.json', '<<<<<<< HEAD\n{}\n=======\n{}\n>>>>>>> otra\n')
        code, _, err = self.run_main(['upsert', '--ns', 'app', '--code', 'global.save', '--values', '-', '--apply'],
                                     self.api, stdin='{"es": "Guardar ya", "pt": "Guardar"}')
        self.assertEqual(code, 1)
        self.assertIn('no es JSON válido', err)
        self.assertEqual(self.api.methods(), [])
        self.assertEqual(json.loads(self.es.read_text()), {'global.save': 'Guardar'})

    def test_error_local_despues_de_la_api(self):
        self.es.chmod(stat.S_IRUSR)
        code, out, _ = self.run_main(['upsert', '--ns', 'app', '--code', 'global.save', '--values', '-', '--apply'],
                                     self.api, stdin='{"es": "Guardar ya"}')
        self.assertEqual(code, 1)
        self.assertIn('ESCRITO=API', out)
        self.assertIn('ERROR_LOCAL=la API ya está actualizada', out)

    def test_delete_llama_a_la_api_y_borra_en_todos_los_idiomas_locales(self):
        code, out, _ = self.run_main(['delete', '--ns', 'app', '--code', 'global.save'], self.api)
        self.assertIn('MODO=dry-run', out)
        self.assertEqual(self.api.methods(), [])
        self.write('packages/i18n/src/locales/es/translations.json', terms.gen_json({'global.save': 'Guardar', 'otro': 'x'}))
        self.write('packages/i18n/src/locales/fr/translations.json', terms.gen_json({'global.save': 'Enregistrer', 'otro': 'y'}))
        code, out, err = self.run_main(['delete', '--ns', 'app', '--code', 'global.save', '--apply'], self.api)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.api.methods(), [('DELETE', '/terms/7')])
        self.assertEqual(json.loads(self.es.read_text()), {'otro': 'x'})
        fr = self.top / 'packages/i18n/src/locales/fr/translations.json'
        self.assertEqual(json.loads(fr.read_text()), {'otro': 'y'})

    def test_delete_no_deja_un_fichero_vacio(self):
        code, out, _ = self.run_main(['delete', '--ns', 'app', '--code', 'global.save', '--apply'], self.api)
        self.assertIn('se quedaría vacío', out)
        self.assertEqual(json.loads(self.es.read_text()), {'global.save': 'Guardar'})

    def test_delete_de_algo_que_no_existe(self):
        self.assertEqual(self.run_main(['delete', '--ns', 'app', '--code', 'no.hay'], self.api)[0], 1)

    def test_search_columnas_desde_locales_y_saltos_de_linea(self):
        api = FakeApi(['es', 'pt', 'nl'], {'app': [term(1, 'app', 'global.save', es='Guardar\ncambios', pt='Guardar')]})
        code, out, _ = self.run_main(['search', 'guardar'], api)
        self.assertIn('| Namespace | Code | ES | PT | NL |', out)
        self.assertIn('| app | global.save | Guardar ⏎ cambios | Guardar | — |', out)


if __name__ == '__main__':
    unittest.main()
