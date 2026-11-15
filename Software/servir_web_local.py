"""Sirve la web de SICMA a la red local, para validarla antes de publicarla en Cloudflare Pages.

Uso, en el PC del backend y con la API corriendo en el puerto 8000:
    cd Software\\sicma-frontend
    npm run web-local                  compila (dist/sicma-frontend-local) y la sirve
    python ..\\servir_web_local.py      solo la sirve, si ya está compilada
    (o .\\iniciar_sicma.ps1 -WebLocal, que la abre junto con los demás procesos)

Desde otro equipo de la misma red: http://<IP del PC del backend>:8080

Este servidor entrega los archivos de la web y reenvía /api/ a la API local, así la web y la API
quedan en la misma dirección. No usa el túnel ni publica nada en internet. Va por HTTP sin cifrar:
úsalo solo en la red del laboratorio.
"""
import argparse
import http.client
import http.server
import os
import socket
from urllib.parse import urlsplit


AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ_POR_DEFECTO = os.path.join(AQUI, 'sicma-frontend', 'dist', 'sicma-frontend-local', 'browser')

# Solo se reenvían estas cabeceras. Las de Cloudflare (CF-Connecting-IP, CF-Ray) no: así nadie en la
# red puede hacerse pasar por el túnel ni cambiar la IP con que SICMA limita los intentos de ingreso.
CABECERAS_PETICION = {'authorization', 'content-type', 'accept', 'accept-language', 'if-none-match', 'if-modified-since'}
# Las pone este servidor (o no aplican entre dos saltos).
CABECERAS_RESPUESTA_OMITIDAS = {'connection', 'keep-alive', 'transfer-encoding', 'content-length', 'server', 'date'}

# Las mismas de public/_headers (Pages), con la API en la misma dirección que la web.
CABECERAS_SEGURIDAD = {
    'Content-Security-Policy': (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
        "font-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; "
        "form-action 'self'; object-src 'none'"
    ),
    'X-Frame-Options': 'DENY',
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=(), payment=(), usb=()',
}


class Manejador(http.server.SimpleHTTPRequestHandler):
    raiz = RAIZ_POR_DEFECTO
    api = urlsplit('http://127.0.0.1:8000')

    def __init__(self, *args, **kwargs):
        self._sin_cache = False
        super().__init__(*args, directory=self.raiz, **kwargs)

    # ------------------------------------------------------------ registro: solo errores
    def log_request(self, code='-', size='-'):
        if isinstance(code, int) and code >= 400:
            super().log_request(code, size)

    def end_headers(self):
        for nombre, valor in CABECERAS_SEGURIDAD.items():
            self.send_header(nombre, valor)
        if self._sin_cache:
            self.send_header('Cache-Control', 'no-cache')  # index.html: tras recompilar se ve lo nuevo
        super().end_headers()

    # ------------------------------------------------------------ API
    def _es_api(self) -> bool:
        return self.path == '/api' or self.path.startswith('/api/')

    def _reenviar(self):
        largo = int(self.headers.get('Content-Length') or 0)
        cuerpo = self.rfile.read(largo) if largo else None
        cabeceras = {k: v for k, v in self.headers.items() if k.lower() in CABECERAS_PETICION}
        conexion = http.client.HTTPConnection(self.api.hostname, self.api.port or 80, timeout=60)
        try:
            conexion.request(self.command, self.path, body=cuerpo, headers=cabeceras)
            respuesta = conexion.getresponse()
            datos = respuesta.read()
        except OSError:
            self.send_error(502, 'La API de SICMA no responde (¿está corriendo en el puerto 8000?)')
            return
        finally:
            conexion.close()
        self.send_response(respuesta.status, respuesta.reason)
        for nombre, valor in respuesta.getheaders():
            if nombre.lower() not in CABECERAS_RESPUESTA_OMITIDAS:
                self.send_header(nombre, valor)
        self.send_header('Content-Length', str(len(datos)))
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(datos)

    # ------------------------------------------------------------ web (aplicación de una página)
    def _preparar_archivo(self):
        """Las rutas de la aplicación (/panel, /activos/3...) no son archivos: van a index.html."""
        ruta = urlsplit(self.path).path
        if ruta == '/' or not os.path.isfile(self.translate_path(ruta)):
            self.path = '/index.html'
        self._sin_cache = self.path == '/index.html'

    def do_GET(self):
        if self._es_api():
            return self._reenviar()
        self._preparar_archivo()
        return super().do_GET()

    def do_HEAD(self):
        if self._es_api():
            return self._reenviar()
        self._preparar_archivo()
        return super().do_HEAD()

    def _solo_api(self):
        if self._es_api():
            return self._reenviar()
        self.send_error(405)

    do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = _solo_api


def direcciones_locales() -> list[str]:
    try:
        datos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
    except OSError:
        return []
    return sorted({d[4][0] for d in datos if not d[4][0].startswith('127.')})


def main():
    parser = argparse.ArgumentParser(description='Sirve la web de SICMA a la red local.')
    parser.add_argument('--puerto', type=int, default=8080)
    parser.add_argument('--api', default='http://127.0.0.1:8000', help='Dirección de la API (waitress).')
    parser.add_argument('--raiz', default=RAIZ_POR_DEFECTO, help='Carpeta de la web compilada.')
    args = parser.parse_args()

    if not os.path.isfile(os.path.join(args.raiz, 'index.html')):
        raise SystemExit(
            f'No está la web compilada en {args.raiz}.\n'
            'Compílala con:  cd Software\\sicma-frontend  y  npm run web-local'
        )
    Manejador.raiz = args.raiz
    Manejador.api = urlsplit(args.api)

    servidor = http.server.ThreadingHTTPServer(('0.0.0.0', args.puerto), Manejador)
    print(f'Web de SICMA en la red local (API: {args.api}). Ctrl+C para detener.')
    print(f'  En este equipo:     http://localhost:{args.puerto}')
    for ip in direcciones_locales():
        print(f'  Desde otro equipo:  http://{ip}:{args.puerto}')
    print(flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print('Detenido.')


if __name__ == '__main__':
    main()
