"""Pruebas de plugins/desa/scripts/desa_api.py. Uso: python3 -m unittest discover -s tests"""

import contextlib
import http.server
import io
import json
import os
import pathlib
import socket
import stat
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'plugins' / 'desa' / 'scripts'))
import desa_api  # noqa: E402

TOKEN = 'tok-secreto-123'


class Home(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = dict(os.environ)
        os.environ['HOME'] = self.tmp.name
        os.environ.pop('DESA_API_TOKEN', None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.env)
        self.tmp.cleanup()

    def settings(self, data):
        p = pathlib.Path(self.tmp.name, '.claude', 'settings.json')
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data))

    def run_main(self, argv, stdin=None):
        out, err = io.StringIO(), io.StringIO()
        old = sys.stdin
        if stdin is not None:
            sys.stdin = io.StringIO(stdin)
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = desa_api.main(argv)
        finally:
            sys.stdin = old
        return code, out.getvalue(), err.getvalue()


class TokenTest(Home):
    def test_sin_token(self):
        self.assertEqual(desa_api.token_source(), (None, None))

    def test_clave_antigua_de_settings(self):
        self.settings({'desa_wiki_token': TOKEN, 'otra': 1})
        token, source = desa_api.token_source()
        self.assertEqual(token, TOKEN)
        self.assertIn('desa_wiki_token', source)

    def test_orden_de_prioridad(self):
        self.settings({'desa_wiki_token': 'viejo', 'desa_api_token': 'nuevo'})
        self.assertEqual(desa_api.token_source()[0], 'nuevo')
        desa_api.save_token('fichero')
        self.assertEqual(desa_api.token_source()[0], 'fichero')
        os.environ['DESA_API_TOKEN'] = 'entorno'
        self.assertEqual(desa_api.token_source()[0], 'entorno')

    def test_save_token_con_permisos_600(self):
        f = desa_api.save_token('  abc  \n')
        self.assertEqual(f.read_text(), 'abc\n')
        self.assertEqual(stat.S_IMODE(f.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(f.parent.stat().st_mode), 0o700)

    def test_save_token_rechaza_vacio_o_con_espacios(self):
        for bad in ('', '   ', 'a b', 'a\x07b'):
            with self.assertRaises(ValueError):
                desa_api.save_token(bad)

    def test_token_con_salto_de_linea_no_se_usa_ni_se_enseña(self):
        f = desa_api.token_file()
        f.parent.mkdir(parents=True)
        f.write_text(f'{TOKEN}\nsegunda-linea\n')
        self.assertEqual(desa_api.token_source(), (None, str(f)))
        code, out, err = self.run_main(['token-status'])
        self.assertEqual(code, 2)
        self.assertIn('TOKEN_INVALIDO', out)
        self.assertNotIn(TOKEN, out + err)
        code, out, err = self.run_main(['GET', '/documents'])
        self.assertEqual(code, 2)
        self.assertIn('TOKEN_INVALIDO', err)
        self.assertNotIn(TOKEN, out + err)

    def test_token_invalido_en_el_entorno(self):
        os.environ['DESA_API_TOKEN'] = f'{TOKEN}\r\nX: y'
        code, out, err = self.run_main(['GET', '/documents'])
        self.assertEqual(code, 2)
        self.assertNotIn(TOKEN, out + err)

    def test_token_status_no_imprime_el_token(self):
        self.settings({'desa_wiki_token': TOKEN})
        code, out, err = self.run_main(['token-status'])
        self.assertEqual(code, 0)
        self.assertNotIn(TOKEN, out + err)

    def test_set_token_avisa_si_hay_variable_de_entorno(self):
        os.environ['DESA_API_TOKEN'] = 'otro'
        code, out, _ = self.run_main(['set-token', '--stdin'], stdin='nuevo\n')
        self.assertEqual(code, 0)
        self.assertIn('DESA_API_TOKEN está definida', out)

    def test_workdir_privado(self):
        d = desa_api.workdir()
        self.assertEqual(stat.S_IMODE(d.stat().st_mode), 0o700)

    def test_token_con_caracteres_no_ascii(self):
        for bad in (f'{TOKEN}​x', f'{TOKEN}-€', f'{TOKEN}-ñ', f'{TOKEN} x', f'{TOKEN} x'):
            os.environ['DESA_API_TOKEN'] = bad
            self.assertEqual(desa_api.token_source(), (None, 'DESA_API_TOKEN'), repr(bad))
            code, out, err = self.run_main(['token-status'])
            self.assertEqual(code, 2)
            self.assertIn('TOKEN_INVALIDO', out)
            code, out, err = self.run_main(['GET', '/documents'])
            self.assertEqual(code, 2)
            self.assertIn('no ASCII', err)
            self.assertNotIn(TOKEN, out + err)
            with self.assertRaises(ValueError):
                desa_api.save_token(bad)

    def test_fichero_de_token_que_no_es_utf8(self):
        f = desa_api.token_file()
        f.parent.mkdir(parents=True)
        f.write_bytes(b'tok-\xf1-secreto\n')
        self.assertEqual(desa_api.token_source(), (None, str(f)))

    def test_workdir_enlazado_o_colgante_no_se_usa(self):
        fuera = pathlib.Path(self.tmp.name, 'fuera')
        fuera.mkdir(mode=0o755)
        fuera.chmod(0o755)
        wd = pathlib.Path(self.tmp.name, '.cache', 'desa')
        wd.parent.mkdir(parents=True)
        wd.symlink_to(fuera)
        code, out, err = self.run_main(['workdir'])
        self.assertEqual(code, 64)
        self.assertIn('enlace simbólico', err)
        self.assertEqual(stat.S_IMODE(fuera.stat().st_mode), 0o755)
        code, _, err = self.run_main(['GET', '/documents/34', '--save-content', str(fuera / 'x.md')])
        self.assertEqual(code, 64)
        self.assertFalse((fuera / 'x.md').exists())
        wd.unlink()
        wd.symlink_to(pathlib.Path(self.tmp.name, 'no-existe'))
        self.assertEqual(self.run_main(['workdir'])[0], 64)
        wd.unlink()
        wd.write_text('')
        self.assertEqual(self.run_main(['workdir'])[0], 64)


class UrlTest(unittest.TestCase):
    def test_codifica_texto_libre(self):
        url = desa_api.build_url('/documents', [('filter[search]', 'lógica de negocio & más')])
        self.assertEqual(url, desa_api.BASE_URL + '/documents?filter[search]=l%C3%B3gica+de+negocio+%26+m%C3%A1s')

    def test_recodifica_la_query_del_path(self):
        url = desa_api.build_url('/documents?filter[search]=dos palabras&perPage=100')
        self.assertEqual(url, desa_api.BASE_URL + '/documents?filter[search]=dos+palabras&perPage=100')

    def test_solo_rutas_de_wiki_y_terms(self):
        for ok in ('/documents', '/documents/root', '/documents/new', '/documents/34', '/terms', '/terms/new', '/terms/7', '/locales', '/terms/'):
            desa_api.build_url(ok)
        for bad in ('/customers/3/token', '/orders/export', '/documents/../customers', '/documents/34/export',
                    '//otro.example/x', 'https://otro.example/x', '/terms/7/../../x', '/',
                    '/documents/٣٤', '/documents/３４', '/terms/𝟕'):
            with self.assertRaises(ValueError, msg=bad):
                desa_api.build_url(bad)


class Handler(http.server.BaseHTTPRequestHandler):
    seen = []
    redirect_to = None
    payload = None

    def _reply(self, code, payload, headers=None):
        raw = json.dumps(payload).encode()
        self.send_response(code)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _route(self, method, body=None):
        Handler.seen.append((method, self.path, dict(self.headers), body))
        if Handler.redirect_to:
            return self._reply(302, {}, {'Location': Handler.redirect_to})
        if self.path.startswith('/locales'):
            return self._reply(401, {'message': 'Unauthenticated.'})
        if method == 'POST':
            return self._reply(422, {'errors': {'title': ['obligatorio']}})
        if Handler.payload is not None:
            return self._reply(200, Handler.payload)
        return self._reply(200, {'data': {'id': 34, 'fields': {'content': 'Texto **real**\ncon $dolar y `código`'}}})

    def do_GET(self):
        self._route('GET')

    def do_POST(self):
        self._route('POST', self.rfile.read(int(self.headers['Content-Length'])))

    def log_message(self, *args):
        pass


class Otro(Handler):
    seen = []

    def _route(self, method, body=None):
        Otro.seen.append((method, self.path, dict(self.headers), body))
        self._reply(200, {'robado': True})


def serve(handler):
    srv = http.server.HTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


class RequestTest(Home):
    @classmethod
    def setUpClass(cls):
        cls.server, cls.otro = serve(Handler), serve(Otro)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.otro.shutdown()

    def setUp(self):
        super().setUp()
        self.base = desa_api.BASE_URL
        desa_api.BASE_URL = f'http://127.0.0.1:{self.server.server_port}'
        Handler.seen.clear()
        Otro.seen.clear()
        Handler.redirect_to = None
        Handler.payload = None
        self.settings({'desa_wiki_token': TOKEN})

    def tearDown(self):
        desa_api.BASE_URL = self.base
        super().tearDown()

    def test_get_ok_con_cabeceras(self):
        code, out, err = self.run_main(['GET', '/documents', '--param', 'filter[search]=a b'])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)['status'], 200)
        method, path, headers, _ = Handler.seen[0]
        self.assertEqual(path, '/documents?filter[search]=a+b')
        self.assertEqual(headers['Authorization'], f'Bearer {TOKEN}')
        self.assertEqual(headers['Accept'], 'application/json')
        self.assertNotIn(TOKEN, out + err)

    def test_error_http_sale_con_1_y_sin_token(self):
        code, out, err = self.run_main(['GET', '/locales'])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out)['status'], 401)
        self.assertNotIn(TOKEN, out + err)

    def test_no_sigue_redirecciones_ni_reenvia_el_token(self):
        Handler.redirect_to = f'http://localhost:{self.otro.server_port}/robar'
        code, out, _ = self.run_main(['GET', '/documents'])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out)['status'], 302)
        body = pathlib.Path(self.tmp.name, 'b.json')
        body.write_text('{"fields": {}}')
        code, out, _ = self.run_main(['POST', '/terms/7', '--body', str(body)])
        self.assertEqual(code, 1)
        self.assertEqual(Otro.seen, [])

    def test_post_envia_el_fichero_tal_cual(self):
        body = pathlib.Path(self.tmp.name, 'body.json')
        texto = {'fields': {'content': "Código con $request->input(), `backticks` y 'comillas'"}}
        body.write_text(json.dumps(texto, ensure_ascii=False), encoding='utf-8')
        code, out, _ = self.run_main(['POST', '/documents/new', '--body', str(body)])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out)['body']['errors']['title'], ['obligatorio'])
        _, _, headers, sent = Handler.seen[0]
        self.assertEqual(headers['Content-Type'], 'application/json')
        self.assertEqual(json.loads(sent.decode('utf-8')), texto)

    def test_save_content_y_content_from(self):
        wd = desa_api.workdir()
        code, out, _ = self.run_main(['GET', '/documents/34', '--save-content', str(wd / 'actual.md')])
        self.assertEqual(code, 0)
        self.assertEqual((wd / 'actual.md').read_text(), 'Texto **real**\ncon $dolar y `código`')
        (wd / 'nuevo.md').write_text('Texto nuevo con $dolar')
        (wd / 'body.json').write_text('{"fields": {"title": "T", "content": "se sustituye"}}')
        self.run_main(['POST', '/documents/34', '--body', str(wd / 'body.json'), '--content-from', 'nuevo.md'])
        sent = json.loads(Handler.seen[-1][3].decode('utf-8'))
        self.assertEqual(sent['fields'], {'title': 'T', 'content': 'Texto nuevo con $dolar'})

    def test_ficheros_fuera_de_workdir(self):
        fuera = pathlib.Path(self.tmp.name, 'fuera.md')
        self.assertEqual(self.run_main(['GET', '/documents/34', '--save-content', str(fuera)])[0], 64)
        self.assertEqual(self.run_main(['GET', '/documents/34', '--save-content', '../fuera.md'])[0], 64)
        self.assertFalse(fuera.exists())
        self.assertEqual(Handler.seen, [])

    def test_ruta_no_permitida_no_llega_a_la_api(self):
        self.assertEqual(self.run_main(['GET', '/customers/3/token'])[0], 64)
        self.assertEqual(Handler.seen, [])

    def test_post_sin_body_o_con_json_invalido(self):
        self.assertEqual(self.run_main(['POST', '/documents/new'])[0], 64)
        bad = pathlib.Path(self.tmp.name, 'bad.json')
        bad.write_text('{no es json')
        self.assertEqual(self.run_main(['POST', '/documents/new', '--body', str(bad)])[0], 64)
        self.assertEqual(Handler.seen, [])

    def test_get_no_admite_body(self):
        self.assertEqual(self.run_main(['GET', '/documents', '--body', 'x.json'])[0], 64)

    def test_sin_token_sale_con_2(self):
        os.remove(pathlib.Path(self.tmp.name, '.claude', 'settings.json'))
        self.assertEqual(self.run_main(['GET', '/documents'])[0], 2)
        self.assertEqual(Handler.seen, [])

    def test_error_de_red_sale_con_3(self):
        desa_api.BASE_URL = 'http://127.0.0.1:9'
        code, out, err = self.run_main(['GET', '/documents'])
        self.assertEqual(code, 3)
        self.assertNotIn(TOKEN, out + err)

    def test_conexion_cortada_sale_con_3(self):
        s = socket.socket()
        s.bind(('127.0.0.1', 0))
        s.listen(1)

        def cortar():
            conn, _ = s.accept()
            conn.recv(4096)
            conn.close()
        threading.Thread(target=cortar, daemon=True).start()
        desa_api.BASE_URL = f'http://127.0.0.1:{s.getsockname()[1]}'
        code, out, err = self.run_main(['GET', '/documents'])
        s.close()
        self.assertEqual(code, 3)
        self.assertIn('RemoteDisconnected', out)
        self.assertNotIn(TOKEN, out + err)

    def raw_server(self, response, keep_open=False):
        s = socket.socket()
        s.bind(('127.0.0.1', 0))
        s.listen(1)
        self.addCleanup(s.close)

        def serve_once():
            conn, _ = s.accept()
            conn.recv(65536)
            conn.sendall(response)
            if keep_open:
                threading.Event().wait(3)
            conn.close()
        threading.Thread(target=serve_once, daemon=True).start()
        desa_api.BASE_URL = f'http://127.0.0.1:{s.getsockname()[1]}'

    def test_respuesta_de_error_cortada_sale_con_3(self):
        head = b'HTTP/1.1 500 Internal Server Error\r\nContent-Type: application/json\r\nContent-Length: 1000\r\n\r\n{"message": "bo'
        self.raw_server(head)
        code, out, err = self.run_main(['GET', '/documents'])
        self.assertEqual(code, 3, err)
        self.assertIn('respuesta HTTP 500 incompleta: IncompleteRead', json.loads(out)['body']['error'])
        timeout = desa_api.TIMEOUT
        desa_api.TIMEOUT = 0.5
        try:
            self.raw_server(head, keep_open=True)
            code, out, err = self.run_main(['GET', '/documents'])
        finally:
            desa_api.TIMEOUT = timeout
        self.assertEqual(code, 3, err)
        self.assertIn('respuesta HTTP 500 incompleta', out)
        self.assertNotIn(TOKEN, out + err)

    def test_digitos_unicode_en_la_ruta(self):
        self.assertEqual(self.run_main(['GET', '/documents/٣٤'])[0], 64)
        self.assertEqual(Handler.seen, [])

    def test_save_content_al_propio_workdir_o_a_un_directorio_que_no_existe(self):
        wd = desa_api.workdir()
        (wd / 'sub').mkdir()
        for target in (str(wd), '.', 'sub', 'no/existe.md'):
            code, _, err = self.run_main(['GET', '/documents/34', '--save-content', target])
            self.assertEqual(code, 64, target)
            self.assertIn('ERROR=', err)
        self.assertEqual(Handler.seen, [])
        self.assertFalse((wd / 'no').exists())

    def test_save_content_de_algo_que_no_es_un_documento(self):
        wd = desa_api.workdir()
        for payload in ({'data': [{'id': 34}], 'meta': {}}, {'data': {'id': 34}}, {'data': {'fields': {'content': 3}}}, ['x']):
            Handler.payload = payload
            code, out, err = self.run_main(['GET', '/documents', '--save-content', 'lista.md'])
            self.assertEqual(code, 1, payload)
            self.assertIn('no es un documento', err)
            self.assertFalse((wd / 'lista.md').exists())
        Handler.payload = {'data': {'fields': {'content': None}}}
        self.assertEqual(self.run_main(['GET', '/documents/34', '--save-content', 'vacio.md'])[0], 0)
        self.assertEqual((wd / 'vacio.md').read_bytes(), b'')

    def test_saltos_de_linea_tal_cual(self):
        wd = desa_api.workdir()
        texto = 'uno\r\ndos\rtres\n\ncuatro ñ\r\n'
        Handler.payload = {'data': {'id': 34, 'fields': {'content': texto}}}
        code, out, _ = self.run_main(['GET', '/documents/34', '--save-content', 'actual.md'])
        self.assertEqual(code, 0)
        self.assertEqual((wd / 'actual.md').read_bytes(), texto.encode('utf-8'))
        (wd / 'nuevo.md').write_bytes(texto.encode('utf-8'))
        (wd / 'body.json').write_text('{"fields": {"title": "T"}}')
        self.run_main(['POST', '/documents/34', '--body', str(wd / 'body.json'), '--content-from', 'nuevo.md'])
        self.assertEqual(json.loads(Handler.seen[-1][3].decode('utf-8'))['fields']['content'], texto)

    def test_enlace_duro_en_workdir_no_se_usa(self):
        wd = desa_api.workdir()
        fuera = pathlib.Path(self.tmp.name, 'secreto.txt')
        fuera.write_text('no debe salir')
        os.link(fuera, wd / 'nuevo.md')
        (wd / 'body.json').write_text('{"fields": {"title": "T"}}')
        code, _, err = self.run_main(['POST', '/documents/34', '--body', str(wd / 'body.json'), '--content-from', 'nuevo.md'])
        self.assertEqual(code, 64)
        self.assertIn('enlaces duros', err)
        self.assertEqual(self.run_main(['GET', '/documents/34', '--save-content', 'nuevo.md'])[0], 64)
        self.assertEqual(Handler.seen, [])
        self.assertEqual(fuera.read_text(), 'no debe salir')

    def test_content_from_con_un_body_que_no_es_un_objeto(self):
        wd = desa_api.workdir()
        (wd / 'nuevo.md').write_text('x')
        (wd / 'body.json').write_text('[1]')
        self.assertEqual(self.run_main(['POST', '/documents/34', '--body', str(wd / 'body.json'), '--content-from', 'nuevo.md'])[0], 64)
        self.assertEqual(Handler.seen, [])


if __name__ == '__main__':
    unittest.main()
