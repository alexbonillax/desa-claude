"""Pruebas de plugins/desa/scripts/terms.py. Uso: python3 -m unittest discover -s tests"""

import contextlib
import http.client
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
# Backends clonados junto a este repo (p. ej. ~/Docker/app/grupodesa-backend); en CI no hay y se salta.
SIBLING_LANGS = sorted(f for pat in ('*/resources/lang/*/*.php', '*/lang/*/*.php')
                       for f in pathlib.Path(__file__).resolve().parents[2].glob(pat)
                       if terms.LANG_RE.fullmatch(f.parent.name))
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


class BackendLikeApi(FakeApi):
    """Como TermService::get de grupodesa-backend al buscar: solo filtra por los valores no vacíos,
    compara sin distinguir mayúsculas (utf8mb4_unicode_ci) y, sin namespace y code, devuelve un listado."""

    def __call__(self, method, path, params=None, body=None):
        p = dict(params or [])
        if method == 'GET' and path == '/terms' and 'filter[code]' in p:
            self.calls.append((method, path, p, body))
            items = [t for ts in self.terms.values() for t in ts]
            for key in ('namespace', 'code'):
                if p.get(f'filter[{key}]'):
                    items = [t for t in items if t['fields'][key].lower() == p[f'filter[{key}]'].lower()]
            if p.get('filter[namespace]') and p.get('filter[code]'):
                return (200, {'data': items[0]}) if items else (404, None)
            return 200, {'data': items[:5], 'meta': {}}
        return super().__call__(method, path, params, body)


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

    def test_parse_php_escapes_como_bytes(self):
        ok = '<?php\nreturn [\n  "a" => "\\xC3\\xA9xito",\n  "b" => "\\303\\251",\n  "c" => "\\u{e9}\\u{1F600}",\n  "d" => "\\x41\\101",\n];\n'
        self.assertEqual(terms.parse_php(ok), {'a': 'éxito', 'b': 'é', 'c': 'é😀', 'd': 'AA'})
        for bad in ('"\\xE9"', '"\\351"', '"\\377"', '"\\u{D83D}"', '"\\u{110000}"', '"\\xC3"'):
            with self.assertRaises(ValueError, msg=bad):
                terms.parse_php('<?php\nreturn ["a" => ' + bad + '];\n')

    def test_parse_php_rechaza_lo_que_php_lee_distinto_o_no_compila(self):
        h, t = '<?php\nreturn [\n', '];\n'
        for bad in (h + '"a" => "coste $€",\n' + t, h + '"a" => "$ñ",\n' + t, h + '"a" => "$😀",\n' + t,
                    h + '"a" => "¿$¿?",\n' + t,
                    h + "'a' => 'x', // c\r'b' => 'y',\n" + t, h + "'a' => 'x', # c\r'b' => 'y',\n" + t,
                    "<?php // ?><?php return ['a' => 'PHP']; /*\nreturn ['a' => 'parse_php'];\n// */\n",
                    "<?php # ?><?php return ['a' => 'PHP']; /*\nreturn ['a' => 'parse_php'];\n// */\n",
                    h + "#['x' => 'y'],\n'a' => 'b',\n" + t,
                    "<?phpreturn ['a' => 'b'];\n", "<?php/**/return ['a' => 'b'];\n", '<?php',
                    "<?php\nreturn\u00a0['a' => 'b'];\n", "<?php\nreturn\x0c['a' => 'b'];\n", "<?php\nreturn ['a'\x0b=> 'b'];\n",
                    h + '"a" => "\\u{ 41}",\n' + t, h + '"a" => "\\u{0x41}",\n' + t, h + '"a" => "\\u{4_1}",\n' + t,
                    h + '"a" => "\\u{+41}",\n' + t, h + '"a" => "\\u{}",\n' + t, h + '"a" => "\\u{41",\n' + t):
            with self.assertRaises(ValueError, msg=repr(bad)):
                terms.parse_php(bad)

    def test_parse_php_crlf_y_comentarios_validos(self):
        text = "<?php\r\n// comentario\r\n# otro\r\nreturn [\r\n  'a' => \"x\r\ny\", /* ?> */\r\n  'b' => '$€',\r\n];\r\n"
        self.assertEqual(terms.parse_php(text), {'a': 'x\r\ny', 'b': '$€'})

    @unittest.skipUnless(HAS_PHP, 'php no disponible')
    def test_parse_php_lee_lo_mismo_que_php(self):
        h, t = '<?php\nreturn [\n', '];\n'
        cases = [h + '"a" => "\\xC3\\xA9\\303\\251\\u{1F600}\\u{0000e9}",\n' + t, h + '"a" => "\\e\\f\\v\\8\\9\\q\\{\\x\\u0041",\n' + t,
                 h + '"a" => "$5 y $ y $[x] {x} \\$x \\{$",\n' + t, h + "'a' => 'l\\'e\\\\\\n\\x',\n" + t,
                 "<?php\r\n# c\r\nreturn [\r\n'a' => \"x\r\ny\",\r\n];\r\n", '\ufeff<?php\nreturn array("a" => "b");\n']
        with tempfile.TemporaryDirectory() as d:
            for n, text in enumerate(cases):
                p = pathlib.Path(d, f'{n}.php')
                p.write_bytes(text.encode('utf-8'))
                out = subprocess.run(['php', '-n', '-r', 'echo json_encode(array_map("bin2hex", require $argv[1]));', str(p)],
                                     capture_output=True, text=True)
                php = {k: bytes.fromhex(v) for k, v in json.loads(out.stdout.lstrip('\ufeff')).items()}
                self.assertEqual({k: v.encode('utf-8') for k, v in terms.parse_php(text).items()}, php, repr(text))

    @unittest.skipUnless(HAS_PHP and SIBLING_LANGS, 'php o los backends hermanos no disponibles')
    def test_backends_hermanos_se_leen_como_php(self):
        """Los ficheros de idioma planos de los backends clonados junto a este repo se leen igual que con PHP,
        y los de grupodesa-backend (generados por sync) se regeneran con los mismos bytes."""
        read = {}
        for f in SIBLING_LANGS:
            try:
                read[str(f)] = terms.parse_php(f.read_bytes().decode('utf-8'))
            except (ValueError, UnicodeDecodeError):
                pass
        php = subprocess.run(['php', '-n', '-r', 'foreach (array_slice($argv, 1) as $f) $o[$f] = array_map("strval", require $f);'
                              ' echo json_encode($o, JSON_UNESCAPED_UNICODE | JSON_FORCE_OBJECT);', *read],
                             capture_output=True, text=True)
        self.assertEqual(php.returncode, 0, php.stderr)
        self.assertEqual(json.loads(php.stdout), read)
        gd = [f for f in SIBLING_LANGS if f.parts[-5:-3] == ('grupodesa-backend', 'resources') and f.stem not in terms.LARAVEL_OWN]
        for f in gd:
            self.assertIn(str(f), read)
            self.assertEqual(terms.gen_php(read[str(f)]).encode('utf-8'), f.read_bytes(), str(f))

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

    def test_upsert_conserva_en_la_api_los_idiomas_raros_del_term(self):
        api = FakeApi(['es'], {'app': [term(7, 'app', 'global.save', es='Guardar', ca='Desar', **{'../../bootstrap': 'x'})]})
        code, out, err = self.run_main(['upsert', '--ns', 'app', '--code', 'global.save', '--values', '-', '--apply'],
                                       api, stdin='{"es": "Guardar ya"}')
        self.assertEqual(code, 0, err)
        self.assertIn('se conservan en la API y no se escriben en local: ../../bootstrap, ca', out)
        post = [c for c in api.calls if c[0] == 'POST'][0]
        self.assertEqual(post[3]['fields']['value'], {'es': 'Guardar ya', 'ca': 'Desar', '../../bootstrap': 'x'})
        self.assertFalse((self.top / 'packages/i18n/bootstrap').exists())
        self.assertFalse((self.top / 'packages/i18n/src/locales/ca').exists())
        self.assertEqual(json.loads(self.es.read_text()), {'global.save': 'Guardar ya'})

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


class FindTest(Project):
    def setUp(self):
        super().setUp()
        self.es = self.write('packages/i18n/src/locales/es/translations.json',
                             terms.gen_json({'a.primero': 'Primero', 'global.save': 'Guardar'}))

    def test_rechaza_ns_y_code_vacios_o_con_otro_formato(self):
        api = BackendLikeApi(['es'], {'app': [term(1, 'app', 'a.primero', es='Primero'), term(7, 'app', 'global.save', es='G')]})
        for ns, code in (('app', ''), ('', 'global.save'), ('app', 'Global.Save'), ('App', 'global.save'),
                         ('app', 'global.save '), ('sub/dir', 'x'), ('app', 'a..b'), ('app', '.a')):
            for cmd in (['delete', '--apply'], ['find'], ['upsert', '--values', '-', '--apply']):
                code_, _, err = self.run_main([cmd[0], '--ns', ns, '--code', code] + cmd[1:], api, stdin='{"es": "X"}')
                self.assertEqual(code_, 1, (ns, code, cmd))
                self.assertIn('no válido', err)
        self.assertEqual(api.calls, [])
        self.assertEqual(json.loads(self.es.read_text()), {'a.primero': 'Primero', 'global.save': 'Guardar'})

    def test_la_api_devuelve_otro_term(self):
        api = BackendLikeApi(['es'], {'app': [term(7, 'app', 'Global.Save', es='Guardar')]})
        for argv in (['delete', '--ns', 'app', '--code', 'global.save', '--apply'], ['find', '--ns', 'app', '--code', 'global.save'],
                     ['upsert', '--ns', 'app', '--code', 'global.save', '--values', '-', '--apply']):
            code, out, err = self.run_main(argv, api, stdin='{"es": "X"}')
            self.assertEqual(code, 1, argv)
            self.assertIn('la API devolvió otro term al buscar app:global.save: app:Global.Save (id 7)', err)
            self.assertNotIn('NO_EXISTE', out)
        self.assertEqual(api.methods(), [])

    def test_la_api_devuelve_un_listado(self):
        class Listado(FakeApi):
            def __call__(self, method, path, params=None, body=None):
                if method == 'GET' and 'filter[code]' in dict(params or []):
                    self.calls.append((method, path, dict(params), body))
                    return 200, {'data': [term(1, 'app', 'a.primero', es='Primero')], 'meta': {}}
                return super().__call__(method, path, params, body)
        api = Listado(['es'], {})
        code, _, err = self.run_main(['delete', '--ns', 'app', '--code', 'global.save', '--apply'], api)
        self.assertEqual(code, 1)
        self.assertIn('no devolvió un term', err)
        self.assertEqual(api.methods(), [])

    def test_delete_dry_run_enseña_el_term_de_la_api(self):
        api = BackendLikeApi(['es'], {'app': [term(7, 'app', 'global.save', es='Guardar')]})
        code, out, _ = self.run_main(['delete', '--ns', 'app', '--code', 'global.save'], api)
        self.assertEqual(code, 0)
        self.assertIn('TERM=app:global.save id 7', out)


class LocalWriteTest(Project):
    def setUp(self):
        super().setUp()
        self.es = self.write('packages/i18n/src/locales/es/translations.json', terms.gen_json({'global.save': 'Guardar'}))
        self.pt = self.write('packages/i18n/src/locales/pt/translations.json', terms.gen_json({'global.save': 'Guardar'}))
        self.api = FakeApi(['es', 'pt'], {'app': [term(7, 'app', 'global.save', es='Guardar', pt='Guardar')]})

    def upsert(self, values, api=None):
        return self.run_main(['upsert', '--ns', 'app', '--code', 'global.save', '--values', '-', '--apply'],
                             api or self.api, stdin=values)

    def test_surrogate_en_un_json_local_aborta_sin_tocar_la_api(self):
        self.pt.write_text('{\n  "global.save": "Guardar",\n  "icono": "\\ud83d"\n}\n')
        before = (self.es.read_bytes(), self.pt.read_bytes())
        code, _, err = self.upsert('{"es": "Guardar ya", "pt": "Guardar já"}')
        self.assertEqual(code, 1)
        self.assertIn("ERROR=", err)
        self.assertIn("'\\ud83d'", err)
        self.assertEqual(self.api.methods(), [])
        self.assertEqual((self.es.read_bytes(), self.pt.read_bytes()), before)

    def test_surrogate_en_values_aborta_sin_tocar_la_api(self):
        code, _, err = self.upsert('{"es": "Guardar \\ud83d"}')
        self.assertEqual(code, 1)
        self.assertIn('surrogate', err)
        self.assertEqual(self.api.methods(), [])

    def test_surrogate_de_la_api_en_sync_no_escribe_nada(self):
        api = FakeApi(['es', 'pt'], {'app': [term(7, 'app', 'global.save', es='Nuevo', pt='Novo \ud83d')]})
        before = (self.es.read_bytes(), self.pt.read_bytes())
        code, _, err = self.run_main(['sync', '--apply'], api)
        self.assertEqual(code, 1)
        self.assertIn('surrogate', err)
        self.assertEqual((self.es.read_bytes(), self.pt.read_bytes()), before)

    def test_escritura_parcial_en_upsert_dice_que_se_escribio(self):
        self.pt.chmod(stat.S_IRUSR)
        code, out, _ = self.upsert('{"es": "Guardar ya", "pt": "Guardar já"}')
        self.assertEqual(code, 1)
        es, pt = 'packages/i18n/src/locales/es/translations.json', 'packages/i18n/src/locales/pt/translations.json'
        self.assertIn(f'ESCRITO=API + {es}\n', out)
        self.assertIn(f'ERROR_LOCAL=la API ya está actualizada, pero falló la escritura de {pt} (PermissionError', out)
        self.assertIn(f'escritos: {es}; sin escribir: {pt}', out)
        self.assertEqual(json.loads(self.es.read_text()), {'global.save': 'Guardar ya'})
        self.assertEqual(json.loads(self.pt.read_text()), {'global.save': 'Guardar'})

    def test_escritura_parcial_en_sync_dice_que_se_escribio(self):
        self.pt.chmod(stat.S_IRUSR)
        api = FakeApi(['es', 'pt'], {'app': [term(7, 'app', 'global.save', es='Nuevo', pt='Novo')]})
        code, out, err = self.run_main(['sync', '--apply'], api)
        self.assertEqual(code, 1)
        self.assertIn('ESCRITOS=1\n', out)
        self.assertIn('ERROR_LOCAL=falló la escritura de packages/i18n/src/locales/pt/translations.json (PermissionError', out)
        self.assertIn('escritos: packages/i18n/src/locales/es/translations.json;', out)
        self.assertEqual(json.loads(self.es.read_text()), {'global.save': 'Nuevo'})

    def test_escritura_atomica(self):
        self.es.chmod(0o640)
        real_replace = terms.os.replace

        def falla(*a):
            raise OSError('disco lleno')
        terms.os.replace = falla
        try:
            code, out, _ = self.upsert('{"es": "Guardar ya"}')
        finally:
            terms.os.replace = real_replace
        self.assertEqual(code, 1)
        self.assertIn('disco lleno', out)
        self.assertEqual(json.loads(self.es.read_text()), {'global.save': 'Guardar'})
        self.assertEqual(sorted(p.name for p in self.es.parent.iterdir()), ['translations.json'])
        code, _, err = self.upsert('{"es": "Guardar ya"}')
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(self.es.read_text()), {'global.save': 'Guardar ya'})
        self.assertEqual(stat.S_IMODE(self.es.stat().st_mode), 0o640)
        self.assertEqual(sorted(p.name for p in self.es.parent.iterdir()), ['translations.json'])

    def test_un_enlace_se_escribe_en_su_destino(self):
        real = self.write('packages/i18n/src/locales/es/real.json', terms.gen_json({'global.save': 'Guardar'}))
        self.es.unlink()
        self.es.symlink_to('real.json')
        code, _, err = self.upsert('{"es": "Guardar ya"}')
        self.assertEqual(code, 0, err)
        self.assertTrue(self.es.is_symlink())
        self.assertEqual(json.loads(real.read_text()), {'global.save': 'Guardar ya'})

    def test_error_de_red_de_http_client(self):
        def corta(*a, **k):
            raise http.client.IncompleteRead(b'{"data": [', 100)
        code, out, err = self.run_main(['locales'], corta)
        self.assertEqual(code, 1)
        self.assertIn('ERROR=error de red: IncompleteRead', err)


class BackendFixesTest(Project):
    def setUp(self):
        super().setUp()
        self.write('artisan', '')
        self.app = self.write('resources/lang/es/app.php', terms.gen_php({'a': 'A'}))
        self.auth = self.write('resources/lang/es/auth.php', "<?php\nreturn ['failed' => 'x', 'throttle' => 'y'];\n")
        self.propio = self.write('resources/lang/es/propio.php', terms.gen_php({'z': 'solo local'}))

    def upsert(self, ns, code, api, values='{"es": "Nuevo"}'):
        return self.run_main(['upsert', '--ns', ns, '--code', code, '--values', '-', '--apply'], api, stdin=values)

    def test_escapes_de_bytes_se_leen_como_en_php(self):
        self.app.write_text('<?php\n\nreturn array(\n    "a"  => "A",\n    "ok" => "\\xC3\\xA9xito \\303\\251",\n);\n')
        code, _, err = self.upsert('app', 'nuevo', FakeApi(['es'], {'app': [term(1, 'app', 'a', es='A')]}))
        self.assertEqual(code, 0, err)
        self.assertEqual(terms.load_php(self.app), {'a': 'A', 'nuevo': 'Nuevo', 'ok': 'éxito é'})
        self.assertIn('"éxito é"', self.app.read_text())

    def test_php_que_no_da_utf8_pide_allow_php_y_no_toca_la_api(self):
        self.app.write_text('<?php\n\nreturn array(\n    "a"  => "A",\n    "ok" => "\\xE9xito",\n);\n')
        before = self.app.read_bytes()
        api = FakeApi(['es'], {'app': [term(1, 'app', 'a', es='A')]})
        code, _, err = self.upsert('app', 'nuevo', api)
        self.assertEqual(code, 1)
        self.assertIn('--allow-php', err)
        self.assertEqual(api.methods(), [])
        self.assertEqual(self.app.read_bytes(), before)

    def test_include_ns_sustituye_un_namespace_ajeno(self):
        api = FakeApi(['es'], {'app': [term(1, 'app', 'a', es='A')], 'propio': [term(9, 'propio', 'otra.cosa', es='Otra')]})
        code, out, err = self.run_main(['sync', '--include-ns', 'propio'], api)
        self.assertEqual(code, 0, err)
        self.assertNotIn('NAMESPACE_AJENO', out)
        self.assertIn('resources/lang/es/propio.php: +1 ~0 -1 · bajas: z', out)
        code, out, err = self.run_main(['sync', '--include-ns', 'propio', '--apply'], api)
        self.assertEqual(code, 0, err)
        self.assertEqual(terms.load_php(self.propio), {'otra.cosa': 'Otra'})

    def test_lang_vendor_no_bloquea_nada(self):
        vendor = self.write('resources/lang/vendor/backup/es/notifications.php', "<?php\nreturn ['x' => 'y'];\n")
        self.write('resources/lang/vendor/suelto.php', "<?php\nreturn ['x' => 'y'];\n")
        self.assertIn('NAMESPACES=app propio\n', self.run_main(['project'])[1])
        api = FakeApi(['es'], {'app': [term(1, 'app', 'a', es='A2'), term(2, 'app', 'b', es='B')]})
        for argv, stdin in ((['sync', '--apply'], None), (['upsert', '--ns', 'app', '--code', 'c', '--values', '-', '--apply'], '{"es": "C"}'),
                            (['delete', '--ns', 'app', '--code', 'b', '--apply'], None)):
            code, _, err = self.run_main(argv, api, stdin)
            self.assertEqual(code, 0, (argv, err))
        self.assertEqual(terms.load_php(self.app), {'a': 'A2', 'c': 'C'})
        self.assertEqual(vendor.read_text(), "<?php\nreturn ['x' => 'y'];\n")

    def test_include_ns_de_laravel_o_con_otro_formato(self):
        api = FakeApi(['es'], {'app': [term(1, 'app', 'a', es='A')], 'auth': [term(2, 'auth', 'failed', es='Otra')],
                               '': [term(3, '', 'x', es='X')], 'sub/dir': [term(4, 'sub/dir', 'y', es='Y')]})
        before = self.auth.read_text()
        code, _, err = self.run_main(['sync', '--include-ns', 'auth', '--apply'], api)
        self.assertEqual(code, 1)
        self.assertIn('propio de Laravel', err)
        self.assertEqual(self.auth.read_text(), before)
        for ns in ('', 'sub/dir', '../x', 'App'):
            code, _, err = self.run_main(['sync', '--include-ns', ns, '--apply'], api)
            self.assertEqual(code, 1, ns)
            self.assertIn('namespace no válido', err)
        self.assertEqual(api.calls, [])
        self.assertEqual(sorted(p.name for p in (self.top / 'resources/lang/es').iterdir()), ['app.php', 'auth.php', 'propio.php'])

    def test_upsert_y_delete_en_un_namespace_ajeno(self):
        before = self.propio.read_bytes()
        for terms_propio in ([term(9, 'propio', 'otra.cosa', es='Otra')], []):
            api = FakeApi(['es'], {'propio': terms_propio})
            for apply in ([], ['--apply']):
                code, _, err = self.run_main(['upsert', '--ns', 'propio', '--code', 'nuevo', '--values', '-'] + apply,
                                             api, stdin='{"es": "Nuevo"}')
                self.assertEqual(code, 1)
                self.assertIn('NAMESPACE_AJENO: el namespace propio de este proyecto tiene 1 claves y ninguna está en el propio de la API', err)
                self.assertIn('propondría dar de baja las demás claves locales', err)
            self.assertEqual(api.methods(), [])
        api = FakeApi(['es'], {'propio': [term(9, 'propio', 'otra.cosa', es='Otra')]})
        code, _, err = self.run_main(['delete', '--ns', 'propio', '--code', 'otra.cosa', '--apply'], api)
        self.assertEqual(code, 1)
        self.assertIn('NAMESPACE_AJENO', err)
        self.assertEqual(api.methods(), [])
        self.assertEqual(self.propio.read_bytes(), before)

    def test_upsert_en_un_namespace_compartido_o_solo_de_la_api(self):
        api = FakeApi(['es'], {'app': [term(1, 'app', 'a', es='A')]})
        code, _, err = self.upsert('app', 'nuevo', api)
        self.assertEqual(code, 0, err)
        self.assertEqual(terms.load_php(self.app), {'a': 'A', 'nuevo': 'Nuevo'})
        code, out, err = self.upsert('notifications', 'nuevo', api)
        self.assertEqual(code, 0, err)
        self.assertIn('AVISO=el namespace notifications no existe en local', out)

    def test_ficheros_que_solo_cambian_de_formato(self):
        self.app.write_text("<?php\n\nreturn [\n    // saludo\n    'a' => 'A',\n];\n")
        api = FakeApi(['es'], {'app': [term(1, 'app', 'a', es='A')]})
        code, out, err = self.run_main(['sync'], api)
        self.assertEqual(code, 0, err)
        self.assertIn('resources/lang/es/app.php: +0 ~0 -0 · solo formato', out)
        self.assertIn('CAMBIA_FORMATO=1\n', out)
        self.assertIn('BAJAS=0\n', out)
        api = FakeApi(['es'], {'app': [term(1, 'app', 'a', es='A2')]})
        code, out, err = self.run_main(['sync'], api)
        self.assertIn('resources/lang/es/app.php: +0 ~1 -0 · cambia también el formato', out)
        self.assertIn('CAMBIA_FORMATO=1\n', out)
        self.app.write_bytes(terms.render(self.app, {'a': 'A'}))
        code, out, err = self.run_main(['sync'], api)
        self.assertIn('resources/lang/es/app.php: +0 ~1 -0\n', out)
        self.assertIn('CAMBIA_FORMATO=0\n', out)

    def test_crlf_en_un_php_se_lee_tal_cual(self):
        self.app.write_bytes(b"<?php\r\n\r\nreturn array(\r\n    \"a\" => \"l1\r\nl2\",\r\n);\r\n")
        self.assertEqual(terms.load_php(self.app), {'a': 'l1\r\nl2'})


if __name__ == '__main__':
    unittest.main()
