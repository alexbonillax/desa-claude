#!/usr/bin/env python3
"""Cliente de la API de Grupo Desa (api2.grupodesa.app) para /desa:wiki y /desa:translations.

El token nunca se imprime ni aparece en un comando, y solo se envía a BASE_URL: no se siguen
redirecciones y solo se admiten las rutas de la wiki y de terms.

  desa_api.py token-status                 OK y de dónde sale, NO_TOKEN o TOKEN_INVALIDO
  desa_api.py set-token [--stdin]          guarda el token en ~/.config/desa/api-token (600)
  desa_api.py workdir                      directorio privado (700) para bodies y copias
  desa_api.py GET PATH [--param K=V ...] [--save-content FICHERO]
  desa_api.py POST PATH --body FICHERO.json [--content-from FICHERO] [--param K=V ...]
  desa_api.py DELETE PATH

PATH: /documents, /documents/root, /documents/new, /documents/{id}, /terms, /terms/new,
/terms/{id} o /locales; los parámetros, siempre con --param. --save-content guarda el
fields.content de la respuesta y --content-from lo toma de un fichero, los dos dentro de workdir.

Las peticiones imprimen {"status": N, "body": ...}. Exit: 0 si la respuesta es 2xx,
1 si la API responde con error (también un 3xx), 2 sin token o con un token inválido,
3 error de red, 64 uso incorrecto.
"""

import getpass
import http.client
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = 'https://api2.grupodesa.app'
TIMEOUT = 60
ALLOWED_PATH = re.compile(r'^/(documents(/(root|new|\d+))?|terms(/(new|\d+))?|locales)$')


def home():
    return pathlib.Path(os.environ.get('HOME') or pathlib.Path.home())


def token_file():
    return home() / '.config' / 'desa' / 'api-token'


def settings_file():
    return home() / '.claude' / 'settings.json'


def workdir():
    d = home() / '.cache' / 'desa'
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    return d


def valid_token(t):
    return bool(t) and not any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in t)


def token_source():
    """(token, fuente) del primer token definido. Si esa fuente tiene un token con espacios o
    caracteres de control, devuelve (None, fuente): el valor no se usa ni se enseña."""
    candidates = [(os.environ.get('DESA_API_TOKEN', ''), 'DESA_API_TOKEN')]
    f = token_file()
    if f.is_file():
        candidates.append((f.read_text(encoding='utf-8'), str(f)))
    try:
        s = json.loads(settings_file().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        s = {}
    if isinstance(s, dict):
        for key in ('desa_api_token', 'desa_wiki_token'):
            candidates.append((str(s.get(key) or ''), f'{settings_file()} ({key})'))
    for raw, source in candidates:
        t = raw.strip()
        if t:
            return (t, source) if valid_token(t) else (None, source)
    return None, None


def save_token(token):
    token = token.strip()
    if not valid_token(token):
        raise ValueError('token vacío o con espacios o caracteres de control')
    f = token_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(f.parent, 0o700)
    fd = os.open(f, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as out:
        out.write(token + '\n')
    os.chmod(f, 0o600)
    return f


class NoToken(Exception):
    """Sin token, o con un token inválido en la fuente que se indica."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def build_url(path, params=None):
    if not path.startswith('/'):
        path = '/' + path
    parts = urllib.parse.urlsplit(path)
    if parts.scheme or parts.netloc:
        raise ValueError('PATH debe ser una ruta de la API, no una URL')
    clean = parts.path.rstrip('/') or '/'
    if not ALLOWED_PATH.match(clean):
        raise ValueError(f'ruta no permitida: {clean} (solo /documents…, /terms… y /locales)')
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    query += list(params or [])
    url = BASE_URL + clean
    if query:
        url += '?' + urllib.parse.urlencode(query, safe='[]')
    return url


def request(method, path, params=None, body=None):
    """Devuelve (status, body_parseado). status None si hay error de red."""
    token, source = token_source()
    if not token:
        raise NoToken(source)
    url = build_url(path, params)
    headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/json'}
    data = None
    if body is not None:
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with _OPENER.open(req, timeout=TIMEOUT) as resp:
            return resp.status, _parse(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, _parse(e.read())
    except urllib.error.URLError as e:
        return None, {'error': str(e.reason)}
    except (OSError, http.client.HTTPException) as e:
        return None, {'error': f'{type(e).__name__}: {e}'}


def _parse(raw):
    text = raw.decode('utf-8', errors='replace')
    try:
        return json.loads(text) if text.strip() else None
    except ValueError:
        return text


def _in_workdir(value):
    p = pathlib.Path(value).expanduser()
    wd = workdir().resolve()
    target = (p if p.is_absolute() else wd / p).resolve()
    if target != wd and wd not in target.parents:
        raise ValueError(f'el fichero tiene que estar dentro de {wd}')
    return target


def _usage(msg):
    print(f'ERROR={msg}', file=sys.stderr)
    return 64


def _no_token(source):
    if source:
        print(f'TOKEN_INVALIDO en {source}: tiene espacios o caracteres de control', file=sys.stderr)
    else:
        print('NO_TOKEN', file=sys.stderr)
    return 2


def main(argv):
    if not argv:
        return _usage('falta el comando (ver la cabecera de desa_api.py)')
    cmd, rest = argv[0], argv[1:]

    if cmd == 'token-status':
        token, source = token_source()
        if token:
            print(f'OK {source}')
            return 0
        if source:
            print(f'TOKEN_INVALIDO {source}')
        else:
            print('NO_TOKEN')
        return 2

    if cmd == 'set-token':
        token = sys.stdin.readline() if '--stdin' in rest else getpass.getpass('Token de la API de Grupo Desa: ')
        try:
            print(f'Token guardado en {save_token(token)}')
        except ValueError as e:
            return _usage(str(e))
        if os.environ.get('DESA_API_TOKEN', '').strip():
            print('AVISO=DESA_API_TOKEN está definida y tiene prioridad sobre el fichero: quítala o actualízala')
        return 0

    if cmd == 'workdir':
        print(workdir())
        return 0

    if cmd not in ('GET', 'POST', 'DELETE'):
        return _usage(f'comando no reconocido: {cmd}')
    if not rest or rest[0].startswith('--'):
        return _usage('falta PATH')
    path, rest = rest[0], rest[1:]
    params, body, save_to, content_from = [], None, None, None
    i = 0
    try:
        while i < len(rest):
            opt = rest[i]
            val = rest[i + 1] if i + 1 < len(rest) else None
            if opt == '--param' and val and '=' in val:
                params.append(tuple(val.split('=', 1)))
            elif opt == '--body' and val and cmd == 'POST':
                raw = pathlib.Path(val).read_bytes()
                json.loads(raw.decode('utf-8'))
                body = raw
            elif opt == '--content-from' and val and cmd == 'POST':
                content_from = _in_workdir(val)
            elif opt == '--save-content' and val and cmd == 'GET':
                save_to = _in_workdir(val)
            else:
                return _usage(f'opción no válida para {cmd}: {opt}')
            i += 2
        if cmd == 'POST' and body is None:
            return _usage('POST necesita --body FICHERO.json')
        if content_from is not None:
            doc = json.loads(body.decode('utf-8'))
            doc.setdefault('fields', {})['content'] = content_from.read_text(encoding='utf-8')
            body = json.dumps(doc, ensure_ascii=False).encode('utf-8')
        build_url(path, params)
    except (OSError, ValueError) as e:
        return _usage(str(e))

    try:
        status, parsed = request(cmd, path, params, body)
    except NoToken as e:
        return _no_token(e.args[0] if e.args else None)
    print(json.dumps({'status': status, 'body': parsed}, ensure_ascii=False, indent=1))
    if status is None:
        return 3
    if save_to is not None and 200 <= status < 300:
        content = ((parsed or {}).get('data') or {}).get('fields', {}).get('content') if isinstance(parsed, dict) else None
        save_to.write_text(content or '', encoding='utf-8')
        print(f'CONTENIDO_GUARDADO={save_to}')
    return 0 if 200 <= status < 300 else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
