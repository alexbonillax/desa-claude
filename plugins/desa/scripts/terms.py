#!/usr/bin/env python3
"""Terms (traducciones) de Grupo Desa: API y ficheros locales, para /desa:translations.

  terms.py project                              tipo de proyecto, raíz de idiomas y namespaces
  terms.py locales                              idiomas de la API
  terms.py find --ns NS --code CODE             el term, o NO_EXISTE
  terms.py search TEXTO [--page N]              tabla con un idioma por columna
  terms.py upsert --ns NS --code CODE --values FICHERO|- [--apply]
  terms.py delete --ns NS --code CODE [--apply]
  terms.py sync [--apply] [--include-ns NS ...]

Sin --apply no escribe nada: enseña qué haría. Con --apply escribe en la API (upsert, delete)
y en los ficheros de idioma del proyecto. Los cambios locales se calculan antes de escribir en
la API: si no se pueden calcular, no se escribe nada. Cualquier error de la API aborta sin escribir.

Los ficheros PHP se leen sin ejecutarlos. Si alguno no tiene el formato plano que genera este
script (o uno equivalente), hace falta --allow-php para cargarlo con PHP, que ejecuta el fichero.
"""

import contextlib
import errno
import http.client
import json
import os
import pathlib
import re
import shutil
import stat
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import desa_api  # noqa: E402

LARAVEL_OWN = {'auth', 'validation', 'passwords', 'pagination', 'errors'}
KNOWN_BACKEND_NS = ['app', 'export', 'notifications', 'paper-catalog']
# code: la regex de TermRequest (grupodesa-backend). namespace: TermRequest solo admite una lista
# (in:app,notifications,paper-catalog); aquí basta con el mismo formato que un segmento de code.
NS_RE = re.compile(r'[a-z0-9]+([_-][a-z0-9]+)*')
CODE_RE = re.compile(r'[a-z0-9]+([_-][a-z0-9]+)*(\.[a-z0-9]+([_-][a-z0-9]+)*)*')
LANG_RE = re.compile(r'[A-Za-z]{2,3}([_-][A-Za-z0-9]{2,8})*')
ALLOW_PHP = False


class Abort(Exception):
    pass


class WriteError(Abort):
    """Falló la escritura de pending[0]; done ya estaban escritos."""

    def __init__(self, done, pending, error):
        self.done, self.pending, self.error = done, pending, error
        super().__init__(f"falló la escritura de {pending[0]} ({type(error).__name__}: {error}); "
                         f"escritos: {', '.join(done) or 'ninguno'}; sin escribir: {', '.join(pending)}")


# --- API ---------------------------------------------------------------------------------

def api(method, path, params=None, body=None, ok=(200, 201)):
    try:
        status, data = desa_api.request(method, path, params, body)
    except desa_api.NoToken as e:
        src = e.args[0] if e.args else None
        raise Abort(f'TOKEN_INVALIDO en {src}' if src else 'NO_TOKEN: no hay token de la API (ver /desa:translations, Paso 2)')
    if status is None:
        raise Abort(f'error de red: {data}')
    if status not in ok:
        raise Abort(f'HTTP {status} en {method} {path}: {json.dumps(data, ensure_ascii=False)[:500]}')
    return status, data


def clean_value(v):
    """value de la API como dict idioma → texto no vacío; [] o null cuentan como vacíos."""
    if not isinstance(v, dict):
        return {}
    return {k: t for k, t in v.items() if isinstance(k, str) and isinstance(t, str) and t.strip()}


def clean_term(t):
    t = dict(t)
    t['fields'] = dict(t.get('fields') or {})
    t['fields']['value'] = clean_value(t['fields'].get('value'))
    return t


def api_locales():
    _, data = api('GET', '/locales')
    return [loc['fields']['code'] for loc in data['data']]


def api_find(ns, code):
    """El term ns:code exacto, o None si no existe. La API solo filtra por los valores que llegan y
    compara sin distinguir mayúsculas: si devuelve otro term (o un listado), se aborta."""
    status, data = api('GET', '/terms', [('filter[code]', code), ('filter[namespace]', ns)], ok=(200, 404))
    if status == 404:
        return None
    term = data.get('data') if isinstance(data, dict) else None
    if not isinstance(term, dict):
        raise Abort(f'la API no devolvió un term al buscar {ns}:{code} (llegó {type(term).__name__}): no se usa')
    fields = term.get('fields') if isinstance(term.get('fields'), dict) else {}
    if fields.get('code') != code or fields.get('namespace') != ns:
        raise Abort(f"la API devolvió otro term al buscar {ns}:{code}: {fields.get('namespace')}:{fields.get('code')} "
                    f"(id {term.get('id')}); no se usa")
    return clean_term(term)


def api_all_terms(ns):
    terms, page = [], 1
    while True:
        _, data = api('GET', '/terms', [('filter[namespace]', ns), ('perPage', '100'),
                                        ('sort[by]', 'code'), ('sort[dir]', 'asc'), ('page', str(page))])
        terms.extend(clean_term(t) for t in data['data'])
        if not data.get('meta', {}).get('has_more_pages'):
            return terms
        page += 1


# --- Formatos de fichero -----------------------------------------------------------------

def php_str(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$') + '"'


def gen_php(d):
    w = max((len(php_str(k)) for k in d), default=0)
    lines = ''.join(f'    {php_str(k).ljust(w)} => {php_str(v)},\n' for k, v in sorted(d.items()))
    return '<?php\n\nreturn array(\n' + lines + ');\n'


def gen_json(d):
    return json.dumps(dict(sorted(d.items())), ensure_ascii=False, indent=2) + '\n'


_DQ_ESC = {'n': b'\n', 't': b'\t', 'r': b'\r', 'v': b'\v', 'e': b'\x1b', 'f': b'\f', '\\': b'\\', '$': b'$', '"': b'"'}
_WS = ' \t\r\n'
_TOKEN = re.compile(r'''[ \t\r\n]+|//[^\n]*|\#(?!\[)[^\n]*|/\*.*?\*/|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|=>|[(),;\[\]]|array\b|return\b''', re.S)


def _dq(body):
    """Texto entre comillas dobles como lo lee PHP: \\x y los octales son bytes, \\u{} es UTF-8 y
    el resultado tiene que ser UTF-8 válido."""
    out, i = bytearray(), 0
    while i < len(body):
        c, n = body[i], body[i + 1:i + 2]
        if c == '$' and n and (n in '_{' or not n.isascii() or n.isalpha()):
            raise ValueError('interpolación de variables')
        if c == '{' and n == '$':
            raise ValueError('interpolación de variables')
        if c != '\\' or not n:
            out += c.encode('utf-8', 'surrogatepass')
            i += 1
            continue
        if n in _DQ_ESC:
            out += _DQ_ESC[n]
            i += 2
        elif n in '01234567':
            m = re.match(r'[0-7]{1,3}', body[i + 1:])
            out.append(int(m.group(0), 8) & 0xFF)
            i += 1 + len(m.group(0))
        elif n in 'xX' and re.match(r'[0-9A-Fa-f]', body[i + 2:i + 3]):
            m = re.match(r'[0-9A-Fa-f]{1,2}', body[i + 2:])
            out.append(int(m.group(0), 16))
            i += 2 + len(m.group(0))
        elif n == 'u' and body[i + 2:i + 3] == '{':
            m = re.match(r'\{([0-9A-Fa-f]+)\}', body[i + 2:])
            if not m or int(m.group(1), 16) > 0x10FFFF:
                raise ValueError(f'escape \\u{{}} no válido: {body[i:i + 12]!r}')
            out += chr(int(m.group(1), 16)).encode('utf-8', 'surrogatepass')
            i += 2 + len(m.group(0))
        else:
            out += ('\\' + n).encode('utf-8', 'surrogatepass')
            i += 2
    try:
        return out.decode('utf-8')
    except UnicodeDecodeError:
        raise ValueError(f'los escapes dan texto que no es UTF-8 válido: {body[:40]!r}')


def _sq(body):
    return re.sub(r"\\([\\'])", r'\1', body)


def parse_php(text):
    """Lee un fichero de idioma plano (return array(...) o [...] de pares texto => texto) sin
    ejecutarlo. Lanza ValueError si tiene cualquier otra cosa o algo que PHP leería distinto."""
    text = text.lstrip('\ufeff')
    if not re.match(r'<\?php[ \t\r\n]', text):
        raise ValueError('no empieza por <?php y un espacio o salto de línea')
    toks, pos = [], 5
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m:
            raise ValueError(f'sintaxis no admitida cerca de: {text[pos:pos + 30]!r}')
        tok = m.group(0)
        pos = m.end()
        if tok.startswith(('//', '#')) and ('?>' in tok or '\r' in tok.rstrip('\r')):
            raise ValueError(f'comentario de una línea con ?> o un retorno de carro suelto: {tok[:30]!r}')
        if tok[0] in _WS or tok.startswith(('//', '#', '/*')):
            continue
        if tok.startswith('"'):
            toks.append(('s', _dq(tok[1:-1])))
        elif tok.startswith("'"):
            toks.append(('s', _sq(tok[1:-1])))
        else:
            toks.append(('p', tok))
    seq = [t[1] if t[0] == 'p' else None for t in toks]
    if seq[:1] != ['return']:
        raise ValueError('no es un return de un array')
    if seq[1:3] == ['array', '(']:
        body, close = toks[3:], ')'
    elif seq[1:2] == ['[']:
        body, close = toks[2:], ']'
    else:
        raise ValueError('no es un return de un array')
    if [t[1] for t in body[-2:]] != [close, ';']:
        raise ValueError('el array no termina en ); o ];')
    body = body[:-2]
    out, i = {}, 0
    while i < len(body):
        k, arrow, v = (body[i:i + 3] + [(None, None)] * 3)[:3]
        if k[0] != 's' or arrow != ('p', '=>') or v[0] != 's':
            raise ValueError('hay algo que no es un par texto => texto')
        out[k[1]] = v[1]
        i += 3
        if i < len(body):
            if body[i] != ('p', ','):
                raise ValueError('falta una coma entre pares')
            i += 1
    return out


def read_text(path):
    """Texto UTF-8 del fichero, sin traducir los saltos de línea (PHP lee \\r\\n tal cual)."""
    try:
        return path.read_bytes().decode('utf-8')
    except UnicodeDecodeError:
        raise Abort(f'{path} no es UTF-8 válido')


def load_php(path):
    text = read_text(path)
    try:
        return parse_php(text)
    except ValueError as e:
        if not ALLOW_PHP:
            raise Abort(f'{path} no tiene el formato plano esperado ({e}); leerlo exige ejecutarlo con PHP: repite con --allow-php si confías en el fichero')
    if not shutil.which('php'):
        raise Abort(f'hace falta php para leer {path}')
    out = subprocess.run(['php', '-d', 'display_errors=stderr', '-r',
                          'echo json_encode(require $argv[1], JSON_UNESCAPED_UNICODE);', str(path)],
                         capture_output=True, text=True)
    try:
        data = json.loads(out.stdout) if out.returncode == 0 else None
    except ValueError:
        data = None
    if data is None:
        raise Abort(f'no se pudo leer {path} con php: {out.stderr.strip()[:300]}')
    return _flat(data or {}, path)


def load_json(path):
    try:
        return _flat(json.loads(read_text(path)), path)
    except ValueError as e:
        raise Abort(f'{path} no es JSON válido: {e}')


def _flat(d, path):
    if not isinstance(d, dict) or any(not isinstance(v, str) for v in d.values()):
        raise Abort(f'{path} no es un mapa plano clave → texto; no se toca')
    return d


# --- Proyecto ----------------------------------------------------------------------------

def find_project():
    try:
        top = subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True, check=True).stdout.strip()
        top = pathlib.Path(top)
        git = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        top, git = pathlib.Path.cwd(), False
    fe = top / 'packages' / 'i18n' / 'src' / 'locales'
    if fe.is_dir():
        return {'kind': 'frontend', 'top': top, 'root': fe, 'git': git}
    for rel in ('resources/lang', 'lang'):
        if (top / rel).is_dir():
            return {'kind': 'backend', 'top': top, 'root': top / rel, 'git': git}
    return {'kind': 'no-project', 'top': top, 'root': None, 'git': git}


def local_namespaces(proj):
    if proj['kind'] == 'frontend':
        return ['app']
    if proj['kind'] != 'backend':
        return []
    names = {p.stem for lang in local_langs(proj) for p in (proj['root'] / lang).glob('*.php')} - LARAVEL_OWN
    return sorted(names)


def local_langs(proj):
    """Subdirectorios con nombre de idioma; los demás (lang/vendor de Laravel) no se tocan."""
    if not proj['root']:
        return []
    return sorted(p.name for p in proj['root'].iterdir() if p.is_dir() and LANG_RE.fullmatch(p.name))


def file_for(proj, lang, ns):
    if not LANG_RE.fullmatch(lang or ''):
        raise Abort(f'código de idioma no válido: {lang!r}')
    path = proj['root'] / lang / ('translations.json' if proj['kind'] == 'frontend' else f'{ns}.php')
    root = proj['root'].resolve()
    if root not in path.resolve().parents:
        raise Abort(f'{path} queda fuera de {root}')
    return path


def read_file(path):
    if not path.exists():
        return None
    return load_json(path) if path.suffix == '.json' else load_php(path)


def render(path, d):
    """Bytes del fichero; aborta si el texto no se puede escribir en UTF-8 (un surrogate suelto)."""
    text = gen_json(d) if path.suffix == '.json' else gen_php(d)
    try:
        return text.encode('utf-8')
    except UnicodeEncodeError as e:
        raise Abort(f'{path} no se puede escribir en UTF-8: tendría {e.object[e.start:e.end]!r} (un surrogate suelto, '
                    'del propio fichero o de la API); no se escribe nada')


def rel(proj, path):
    return str(path.relative_to(proj['top']))


def dirty(proj, paths):
    if not proj['git']:
        return None
    rels = [rel(proj, p) for p in paths]
    if not rels:
        return []
    out = subprocess.run(['git', '-C', str(proj['top']), 'status', '--porcelain', '--', *rels],
                         capture_output=True, text=True)
    return [line[3:] for line in out.stdout.splitlines() if line.strip()]


def _umask():
    mask = os.umask(0)
    os.umask(mask)
    return mask


def write_atomic(path, data):
    """Escribe en un temporal del mismo directorio y lo sustituye con os.replace: el fichero queda
    entero o como estaba. Respeta los ficheros de solo lectura, los permisos y los enlaces."""
    path = pathlib.Path(os.path.realpath(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if not os.access(path, os.W_OK):
            raise PermissionError(errno.EACCES, 'sin permiso de escritura', str(path))
        mode = stat.S_IMODE(path.stat().st_mode)
    else:
        mode = 0o666 & ~_umask()
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f'.{path.name}.', suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def write_all(proj, writes):
    """writes: [(path, bytes)]. Devuelve las rutas escritas; si una falla, lanza WriteError con lo
    ya escrito y lo que queda sin escribir."""
    done = []
    for n, (path, data) in enumerate(writes):
        try:
            write_atomic(path, data)
        except Exception as e:
            raise WriteError(done, [rel(proj, p) for p, _ in writes[n:]], e)
        done.append(rel(proj, path))
    return done


# --- Comandos ----------------------------------------------------------------------------

def cmd_project(_args):
    proj = find_project()
    print(f"PROYECTO={proj['kind']}")
    if proj['root']:
        print(f"RAIZ={rel(proj, proj['root'])}")
        print(f"NAMESPACES={' '.join(local_namespaces(proj))}")
    return 0


def cmd_locales(_args):
    print(' '.join(api_locales()))
    return 0


def cmd_find(args):
    term = api_find(args['ns'], args['code'])
    print(json.dumps(term, ensure_ascii=False, indent=1) if term else 'NO_EXISTE')
    return 0


def cell(text):
    return (text or '—').replace('|', '\\|').replace('\r', '').replace('\n', ' ⏎ ')


def cmd_search(args):
    locales = api_locales()
    params = [('filter[search]', args['text']), ('perPage', '25'), ('sort[by]', 'code'),
              ('sort[dir]', 'asc'), ('page', str(args.get('page') or 1))]
    _, data = api('GET', '/terms', params)
    head = ['Namespace', 'Code'] + [code.upper() for code in locales]
    print('| ' + ' | '.join(head) + ' |')
    print('|' + '---|' * len(head))
    for term in data['data']:
        f = clean_term(term)['fields']
        cells = [f.get('namespace', ''), f.get('code', '')] + [cell(f['value'].get(code)) for code in locales]
        print('| ' + ' | '.join(cell(c) for c in cells[:2]) + ' | ' + ' | '.join(cells[2:]) + ' |')
    meta = data.get('meta', {})
    print(f"\nPAGINA={meta.get('page')} TOTAL={meta.get('total')} HAY_MAS={'si' if meta.get('has_more_pages') else 'no'}")
    return 0


def _read_values(src):
    try:
        raw = sys.stdin.read() if src == '-' else pathlib.Path(src).read_text(encoding='utf-8')
        values = json.loads(raw)
    except (OSError, ValueError) as e:
        raise Abort(f'--values no se puede leer como JSON: {e}')
    if not isinstance(values, dict) or not values:
        raise Abort('--values debe ser un objeto JSON {"es": "...", ...} con al menos un idioma')
    for lang, text in values.items():
        if not isinstance(text, str) or not text.strip():
            raise Abort(f'valor vacío o no textual para "{lang}": no se envían cadenas vacías')
        try:
            text.encode('utf-8')
        except UnicodeEncodeError:
            raise Abort(f'el valor de "{lang}" tiene un surrogate suelto (p. ej. \\ud83d): no es UTF-8 válido')
    return values


def _check_ns(proj, ns):
    if proj['kind'] == 'backend' and ns in LARAVEL_OWN:
        raise Abort(f'{ns} es un fichero propio de Laravel: no viene de la API y no se toca')


def local_keys(proj, ns):
    """Claves del namespace en los ficheros locales de un backend; vacío si no existe en local."""
    if proj['kind'] != 'backend' or ns not in local_namespaces(proj):
        return set()
    keys = set()
    for lang in local_langs(proj):
        keys |= set(read_file(file_for(proj, lang, ns)) or {})
    return keys


def foreign_ns(proj, ns, terms=None):
    """Claves locales del namespace si ninguna está en el mismo namespace de la API (es otro
    namespace que se llama igual); vacío si no lo es. Sin terms, los pide a la API si hace falta."""
    keys = local_keys(proj, ns)
    if not keys:
        return set()
    if terms is None:
        terms = api_all_terms(ns)
    return set() if keys & {t['fields']['code'] for t in terms} else keys


def _check_foreign(proj, ns, why):
    keys = foreign_ns(proj, ns)
    if keys:
        raise Abort(f'NAMESPACE_AJENO: el namespace {ns} de este proyecto tiene {len(keys)} claves y ninguna está en el {ns} '
                    f'de la API, así que son dos namespaces distintos con el mismo nombre; no se escribe nada: {why}')


def _local_plan(proj, ns, code, values, remove=False):
    """[(path, bytes)] a escribir, calculado y codificado sin escribir nada."""
    if proj['kind'] == 'no-project':
        return []
    if proj['kind'] == 'frontend' and ns != 'app':
        print(f'AVISO=en frontend solo se sincroniza el namespace app; {ns} queda solo en la API')
        return []
    if proj['kind'] == 'backend' and ns not in local_namespaces(proj):
        print(f'AVISO=el namespace {ns} no existe en local; se queda solo en la API (sync --include-ns {ns} para crearlo)')
        return []
    writes, restyled = [], []
    langs = sorted(set(local_langs(proj)) | (set() if remove else set(values)))
    for lang in langs:
        path = file_for(proj, lang, ns)
        original = read_file(path)
        current = dict(original or {})
        if remove:
            if code not in current:
                continue
            current.pop(code)
            if not current:
                print(f'AVISO={rel(proj, path)} se quedaría vacío: no se toca')
                continue
        else:
            if lang not in values or current.get(code) == values[lang]:
                continue
            current[code] = values[lang]
            if proj['kind'] == 'frontend' and not path.parent.exists():
                print(f'AVISO=idioma nuevo {lang}: registrarlo en packages/i18n/src/index.js y en la configuración de i18n de web y mobile')
        writes.append((path, render(path, current)))
        if original is not None:
            # Un valor roto (un surrogate suelto) en el fichero actual no impide corregirlo o
            # quitarlo: ese fichero cuenta como reescrito con otro formato.
            try:
                same = render(path, original) == path.read_bytes()
            except Abort:
                same = False
            if not same:
                restyled.append(rel(proj, path))
    if writes:
        print(f'CAMBIA_FORMATO={len(restyled)}')
    if restyled:
        print(f"AVISO=cambia también el formato de {', '.join(restyled)}: se reescribe con el de terms.py y se pierden comentarios y estilo")
    return writes


def _apply_local(proj, writes, api_done):
    try:
        done = write_all(proj, writes)
    except WriteError as e:
        print(f"{api_done}{' + ' + ', '.join(e.done) if e.done else ''}")
        print(f'ERROR_LOCAL=la API ya está actualizada, pero {e}')
        return 1
    print(f"{api_done}{' + ' + ', '.join(done) if done else ''}")
    return 0


def cmd_upsert(args):
    ns, code = args['ns'], args['code']
    proj = find_project()
    _check_ns(proj, ns)
    new = _read_values(args['values'])
    locales = api_locales()
    unknown = sorted(set(new) - set(locales))
    if unknown:
        raise Abort(f"idiomas que no están en /locales: {', '.join(unknown)} (hay: {' '.join(locales)})")
    term = api_find(ns, code)
    _check_foreign(proj, ns, 'si el term se escribiera en el fichero local, el siguiente sync dejaría de verlo como '
                             'ajeno y propondría dar de baja las demás claves locales')
    current = dict(term['fields']['value']) if term else {}
    kept = {k: v for k, v in current.items() if k not in locales}
    if kept:
        print(f"AVISO=el term tiene idiomas que no están en /locales: se conservan en la API y no se escriben en local: {', '.join(sorted(kept))}")
        current = {k: v for k, v in current.items() if k in locales}
    merged = {**current, **new}
    print(f"TERM={ns}:{code} ({'actualizar id ' + str(term['id']) if term else 'crear'})")
    for lang in sorted(merged):
        before, after = current.get(lang), merged[lang]
        mark = 'nuevo' if before is None else ('sobrescribe' if before != after else 'igual')
        print(f'  {lang}: {json.dumps(before, ensure_ascii=False)} → {json.dumps(after, ensure_ascii=False)}  [{mark}]')
    missing = sorted(set(locales) - set(merged))
    if missing:
        print(f"SIN_TRADUCCION={' '.join(missing)}")
    writes = _local_plan(proj, ns, code, merged)
    if writes:
        print(f"LOCAL={', '.join(rel(proj, p) for p, _ in writes)}")
    if not args.get('apply'):
        print('MODO=dry-run (usa --apply para escribir en la API y en los ficheros locales)')
        return 0
    body = {'fields': {'namespace': ns, 'code': code, 'value': {**kept, **merged}}}
    api('POST', f"/terms/{term['id']}" if term else '/terms/new', body=body)
    return _apply_local(proj, writes, 'ESCRITO=API')


def cmd_delete(args):
    ns, code = args['ns'], args['code']
    proj = find_project()
    _check_ns(proj, ns)
    term = api_find(ns, code)
    if not term:
        print('NO_EXISTE')
        return 1
    _check_foreign(proj, ns, 'el term no es de este proyecto; bórralo desde el proyecto que usa el namespace de la API')
    print(f"TERM={term['fields']['namespace']}:{term['fields']['code']} id {term['id']}")
    print(json.dumps(term['fields']['value'], ensure_ascii=False, indent=1))
    writes = _local_plan(proj, ns, code, {}, remove=True)
    if writes:
        print(f"LOCAL={', '.join(rel(proj, p) for p, _ in writes)}")
    if not args.get('apply'):
        print('MODO=dry-run (usa --apply para borrarlo de la API y de los ficheros locales)')
        return 0
    api('DELETE', f"/terms/{term['id']}", ok=(200, 204))
    return _apply_local(proj, writes, 'BORRADO=API')


def plan_sync(proj, locales, terms_by_ns):
    """Devuelve la lista de cambios por fichero, con el contenido ya en bytes, sin escribir nada."""
    plan, seen = [], set()
    for ns, terms in terms_by_ns.items():
        for lang in locales:
            desired = {t['fields']['code']: t['fields']['value'][lang]
                       for t in terms if lang in t['fields']['value']}
            path = file_for(proj, lang, ns)
            if path in seen:
                raise Abort(f'dos namespaces escribirían en el mismo fichero {rel(proj, path)}')
            seen.add(path)
            current = read_file(path)
            if not desired:
                if current is not None:
                    plan.append({'path': path, 'obsolete': True})
                continue
            cur = current or {}
            adds = sorted(set(desired) - set(cur))
            removes = sorted(set(cur) - set(desired))
            changes = sorted(k for k in set(desired) & set(cur) if desired[k] != cur[k])
            content = render(path, desired)
            old = path.read_bytes() if current is not None else None
            if old == content:
                continue
            # ¿El fichero actual tiene otro formato? Entonces reescribirlo pierde comentarios y estilo,
            # también cuando además cambian los datos.
            try:
                restyled = old is not None and render(path, current) != old
            except Abort:
                restyled = True
            plan.append({'path': path, 'new': current is None, 'adds': adds, 'changes': changes,
                         'removes': removes, 'content': content, 'restyled': restyled,
                         'format_only': current is not None and not (adds or changes or removes)})
    return plan


def cmd_sync(args):
    proj = find_project()
    if proj['kind'] == 'no-project':
        raise Abort('sync necesita estar en un proyecto (packages/i18n/src/locales, resources/lang o lang)')
    requested = list(dict.fromkeys(args.get('include_ns') or []))
    if proj['kind'] == 'frontend' and any(ns != 'app' for ns in requested):
        raise Abort('en frontend solo existe el namespace app: todos van al mismo translations.json')
    for ns in requested:
        _check_ns(proj, ns)
    locales = api_locales()
    for lang in locales:
        file_for(proj, lang, 'app')
    wanted = local_namespaces(proj)
    extra = [ns for ns in requested if ns not in wanted]
    candidates = wanted + extra
    if proj['kind'] == 'backend':
        candidates += [ns for ns in KNOWN_BACKEND_NS if ns not in candidates]

    terms_by_ns, skipped, missing, foreign = {}, [], [], []
    for ns in candidates:
        terms = api_all_terms(ns)
        if not terms:
            if ns in wanted:
                skipped.append(ns)
            continue
        if ns not in wanted and ns not in extra:
            missing.append(f'{ns} ({len(terms)} terms)')
            continue
        if ns not in requested:
            keys = foreign_ns(proj, ns, terms)
            if keys:
                foreign.append(f'{ns} ({len(keys)} claves locales, ninguna en la API)')
                continue
        terms_by_ns[ns] = terms

    plan = plan_sync(proj, locales, terms_by_ns)
    print(f"PROYECTO={proj['kind']} RAIZ={rel(proj, proj['root'])}")
    print(f"IDIOMAS={' '.join(locales)}")
    print(f"NAMESPACES={' '.join(terms_by_ns)}")
    if skipped:
        print(f"SIN_TERMS_EN_API={' '.join(skipped)} (no se tocan)")
    if foreign:
        print(f"NAMESPACE_AJENO={'; '.join(foreign)} (no se tocan; con --include-ns se sustituirían por los de la API)")
    if missing:
        print(f"SOLO_EN_API={', '.join(missing)} (no existen en local; añadir con --include-ns para crearlos)")
    removes = restyled = 0
    for item in plan:
        r = rel(proj, item['path'])
        if item.get('obsolete'):
            print(f'OBSOLETO={r} (sin terms en la API para ese idioma; no se borra)')
            continue
        removes += len(item['removes'])
        detail = f" · bajas: {', '.join(item['removes'][:20])}{' …' if len(item['removes']) > 20 else ''}" if item['removes'] else ''
        if item['restyled']:
            restyled += 1
        if item['format_only']:
            detail = ' · solo formato (mismos datos; se reescribe con el formato de terms.py y se pierden comentarios y estilo)'
        elif item['restyled']:
            detail += ' · cambia también el formato (se reescribe con el de terms.py y se pierden comentarios y estilo)'
        tag = 'nuevo ' if item['new'] else ''
        print(f"{r}: {tag}+{len(item['adds'])} ~{len(item['changes'])} -{len(item['removes'])}{detail}")
    writes = [i for i in plan if not i.get('obsolete')]
    print(f'BAJAS={removes}')
    print(f'CAMBIA_FORMATO={restyled}')
    d = dirty(proj, [i['path'] for i in writes])
    print(f"CAMBIOS_SIN_COMMITEAR={'desconocido (no es un repo git)' if d is None else (' '.join(d) or 'ninguno')}")
    new_langs = sorted({i['path'].parent.name for i in writes if i['new'] and not i['path'].parent.exists()})
    if proj['kind'] == 'frontend' and new_langs:
        print(f"IDIOMAS_NUEVOS={' '.join(new_langs)} (registrarlos en packages/i18n/src/index.js)")
    if not writes:
        print('SIN_CAMBIOS')
        return 0
    if not args.get('apply'):
        print(f'MODO=dry-run ({len(writes)} ficheros; usa --apply con los mismos argumentos para escribirlos)')
        return 0
    try:
        done = write_all(proj, [(i['path'], i['content']) for i in writes])
    except WriteError as e:
        print(f'ESCRITOS={len(e.done)}')
        print(f'ERROR_LOCAL={e}')
        return 1
    print(f'ESCRITOS={len(done)}')
    return 0


WRITERS = {'upsert', 'delete', 'sync'}


def parse(argv):
    if not argv:
        raise Abort('falta el comando (ver la cabecera de terms.py)')
    args = {'cmd': argv[0]}
    rest = argv[1:]
    i = 0
    while i < len(rest):
        a = rest[i]
        if a in ('--apply', '--allow-php'):
            if args['cmd'] not in WRITERS:
                raise Abort(f"{a} solo vale con {', '.join(sorted(WRITERS))}")
            args[a[2:].replace('-', '_')] = True
            i += 1
        elif a in ('--ns', '--code', '--values', '--page', '--include-ns') and i + 1 < len(rest):
            key = a[2:].replace('-', '_')
            if key == 'include_ns':
                args.setdefault('include_ns', []).append(rest[i + 1])
            else:
                args[key] = rest[i + 1]
            i += 2
        elif not a.startswith('--') and args['cmd'] == 'search' and 'text' not in args:
            args['text'] = a
            i += 1
        else:
            raise Abort(f'argumento no válido: {a}')
    need = {'find': ['ns', 'code'], 'upsert': ['ns', 'code', 'values'], 'delete': ['ns', 'code'], 'search': ['text']}
    for key in need.get(args['cmd'], []):
        if key not in args:
            raise Abort(f"{args['cmd']} necesita --{key}" if key != 'text' else 'search necesita el texto')
    for ns in ([args['ns']] if 'ns' in args else []) + args.get('include_ns', []):
        if not NS_RE.fullmatch(ns):
            raise Abort(f'namespace no válido: {ns!r} (minúsculas, números y guiones, como app o paper-catalog)')
    if 'code' in args and not CODE_RE.fullmatch(args['code']):
        raise Abort(f"code no válido: {args['code']!r} (el formato de la API: minúsculas, números, - y _ en "
                    "segmentos separados por puntos, como global.save)")
    return args


COMMANDS = {'project': cmd_project, 'locales': cmd_locales, 'find': cmd_find, 'search': cmd_search,
            'upsert': cmd_upsert, 'delete': cmd_delete, 'sync': cmd_sync}


def main(argv):
    global ALLOW_PHP
    try:
        args = parse(argv)
        if args['cmd'] not in COMMANDS:
            raise Abort(f"comando no reconocido: {args['cmd']}")
        ALLOW_PHP = bool(args.get('allow_php'))
        return COMMANDS[args['cmd']](args)
    except Abort as e:
        print(f'ERROR={e}', file=sys.stderr)
        return 1
    except http.client.HTTPException as e:
        print(f'ERROR=error de red: {type(e).__name__}: {e}', file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f'ERROR={type(e).__name__}: {e}', file=sys.stderr)
        return 1
    finally:
        ALLOW_PHP = False


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
