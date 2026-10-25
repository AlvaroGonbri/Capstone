"""Agente del lector biométrico de SICMA (RF-ACC). Corre en el PC conectado al SecuGen Hamster Plus.

    python agente_lector.py prueba                      comprueba el lector y captura una huella
    python agente_lector.py enrolar PER-001             registra la huella de una persona en este PC
    python agente_lector.py listar                      identificadores enrolados en este PC
    python agente_lector.py eliminar PER-001            borra las plantillas de una persona
    python agente_lector.py escuchar                    espera huellas, envía cada intento a SICMA y
                                                        atiende los enrolamientos que se piden desde SICMA

Las plantillas quedan solo en este PC (cifradas). A SICMA viaja únicamente el identificador
reconocido; SICMA decide si el acceso se permite según la persona y sus permisos.
La configuración está en agente_lector.ini (ver agente_lector.ini.example).
"""
import argparse
import configparser
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

from almacen import Almacen
from secugen import ERROR_FEAT_NUMBER, ERROR_TIME_OUT, Lector, SecuGenError

AQUI = os.path.dirname(os.path.abspath(__file__))
CALIDAD_ENROLAMIENTO = 70  # la que usa el ejemplo oficial de SecuGen para registrar
CALIDAD_VERIFICACION = 50  # y para verificar
MUESTRAS_ENROLAMIENTO = 3
PAUSA_TRAS_INTENTO_S = 2   # evita registrar dos veces el mismo dedo apoyado
ESPERA_DEDO_MS = 2000      # cada cuánto, sin dedos, se revisan pendientes y enrolamientos en SICMA
INTENTOS_POR_MUESTRA = 4


class EnrolamientoFallido(Exception):
    pass


def cargar_configuracion(ruta):
    config = configparser.ConfigParser()
    if not config.read(ruta, encoding='utf-8'):
        sys.exit(f'Falta {ruta}. Copia agente_lector.ini.example como agente_lector.ini y complétalo.')
    s = config['sicma']
    datos = {
        'url': s.get('url', 'http://127.0.0.1:8000/api').rstrip('/'),
        'punto_id': s.get('punto_id', '').strip(),
        'clave': s.get('clave', '').strip(),
        'dir_sdk': config['secugen'].get('dir_sdk', '').strip(),
        'plantillas': config['secugen'].get(
            'plantillas', os.path.join(os.environ.get('PROGRAMDATA', AQUI), 'SICMA', 'lector', 'plantillas.dat'),
        ),
    }
    return datos


def ahora_iso():
    return datetime.now(timezone.utc).isoformat()


# ------------------------------------------------------------------ comandos

def prueba(cfg, _args):
    with Lector(cfg['dir_sdk']) as lector:
        print(f'Lector abierto: serie {lector.serie or "(sin serie)"}, imagen {lector.ancho}x{lector.alto} a {lector.dpi} dpi.')
        print('Apoya un dedo en el lector (10 segundos)...')
        plantilla, calidad = lector.capturar(10000, CALIDAD_VERIFICACION)
        print(f'Huella capturada: calidad {calidad}/100, plantilla de {len(plantilla)} bytes. El lector funciona.')


def _solo_consola(_muestra, indicacion):
    print(f'  {indicacion}')


def enrolar_huella(lector, almacen, identificador, avisar=_solo_consola):
    """Captura las muestras del mismo dedo y las guarda en este PC. Lanza EnrolamientoFallido con el motivo.

    `avisar(muestra, indicacion)` informa cada paso (a la consola y, desde SICMA, a su pantalla).
    """
    muestras = []
    while len(muestras) < MUESTRAS_ENROLAMIENTO:
        numero = len(muestras) + 1
        for intento in range(1, INTENTOS_POR_MUESTRA + 1):
            print(f'Muestra {numero} de {MUESTRAS_ENROLAMIENTO}:')
            avisar(numero, 'Apoya el dedo en el lector' if intento == 1 else 'Vuelve a apoyar el dedo')
            try:
                plantilla, calidad = lector.capturar(15000, CALIDAD_ENROLAMIENTO)
            except SecuGenError as error:
                if error.codigo not in (ERROR_TIME_OUT, ERROR_FEAT_NUMBER):
                    raise
                avisar(numero, 'No se leyó bien la huella: apoya el dedo de nuevo, centrado y sin presionar fuerte')
                time.sleep(1.5)
                continue
            if muestras and not lector.coinciden(muestras[0], plantilla)[0]:
                avisar(numero, 'No coincide con la primera muestra: usa el mismo dedo')
                time.sleep(1.5)
                continue
            muestras.append(plantilla)
            print(f'  OK (calidad {calidad}).')
            if len(muestras) < MUESTRAS_ENROLAMIENTO:
                avisar(numero, 'Muestra registrada. Levanta el dedo')
                time.sleep(1.5)
            break
        else:
            raise EnrolamientoFallido(f'No se logró la muestra {len(muestras) + 1} en {INTENTOS_POR_MUESTRA} intentos.')

    # El mismo dedo no puede quedar registrado para dos personas: así nadie se enrola con dos identidades.
    for otro, plantilla in almacen.todas():
        if otro != identificador and lector.coinciden(plantilla, muestras[0])[0]:
            raise EnrolamientoFallido(f'Esa huella ya está enrolada como {otro}.')
    almacen.agregar(identificador, muestras)
    almacen.guardar()
    return f'{len(muestras)} muestras registradas en el lector.'


def enrolar(cfg, args):
    identificador = args.identificador.strip()
    almacen = Almacen(cfg['plantillas'])
    if identificador in almacen.identificadores() and not args.reemplazar:
        sys.exit(f'{identificador} ya está enrolado. Usa --reemplazar para volver a registrarlo.')
    with Lector(cfg['dir_sdk']) as lector:
        try:
            enrolar_huella(lector, almacen, identificador)
        except EnrolamientoFallido as error:
            sys.exit(f'{error} No se guardó nada.')
    print(f'{identificador} enrolado. Lo habitual es enrolar desde SICMA (Personal externo → Enrolar huella).')


def listar(cfg, _args):
    ids = Almacen(cfg['plantillas']).identificadores()
    print('\n'.join(ids) if ids else 'No hay huellas enroladas en este PC.')


def eliminar(cfg, args):
    almacen = Almacen(cfg['plantillas'])
    if not almacen.eliminar(args.identificador.strip()):
        sys.exit(f'{args.identificador} no está enrolado en este PC.')
    almacen.guardar()
    print(f'Plantillas de {args.identificador} eliminadas de este PC.')


def llamar_sicma(cfg, metodo, ruta, datos=None):
    """Petición autenticada como el lector. Devuelve el JSON de la respuesta (None si no trae cuerpo)."""
    peticion = urllib.request.Request(
        f'{cfg["url"]}{ruta}',
        data=json.dumps(datos).encode() if datos is not None else None,
        headers={'Content-Type': 'application/json', 'X-Punto-Acceso': cfg['punto_id'], 'X-Device-Key': cfg['clave']},
        method=metodo,
    )
    with urllib.request.urlopen(peticion, timeout=10) as respuesta:
        cuerpo = respuesta.read()
        return json.loads(cuerpo) if cuerpo else None


def atender_enrolamiento(cfg, lector, almacen):
    """Si SICMA pidió enrolar a alguien en este lector, captura su huella e informa el resultado.

    Devuelve True si atendió un enrolamiento.
    """
    try:
        trabajo = llamar_sicma(cfg, 'GET', '/accesos/lector/enrolamientos/siguiente/')
    except (urllib.error.URLError, TimeoutError, OSError):
        return False  # sin SICMA no hay enrolamientos; el lector sigue funcionando
    if not trabajo:
        return False
    print(f'\n=== ENROLAMIENTO pedido desde SICMA: {trabajo["nombre"]} ({trabajo["identificador"]}) ===')

    def avisar(muestra, indicacion):
        print(f'  {indicacion}')
        try:  # si SICMA no recibe el aviso, el enrolamiento sigue igual
            llamar_sicma(cfg, 'POST', f'/accesos/lector/enrolamientos/{trabajo["id"]}/progreso/',
                         {'muestra': muestra, 'total_muestras': MUESTRAS_ENROLAMIENTO, 'indicacion': indicacion[:120]})
        except (urllib.error.URLError, TimeoutError, OSError):
            pass

    try:
        mensaje, exito = enrolar_huella(lector, almacen, trabajo['identificador'], avisar), True
    except EnrolamientoFallido as error:
        mensaje, exito = str(error), False
    except SecuGenError as error:
        mensaje, exito = f'Falla del lector: {error}', False
    try:
        llamar_sicma(cfg, 'POST', f'/accesos/lector/enrolamientos/{trabajo["id"]}/resultado/', {'exito': exito, 'mensaje': mensaje})
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        print(f'  No se pudo informar el resultado a SICMA: {error}')
    print(f'=== {"Enrolamiento completado" if exito else "Enrolamiento fallido"}: {mensaje} ===\n')
    return True


INTENTOS_VERIFICACION = 3


def verificar_identidad(lector, almacen, identificador, avisar):
    """¿La huella que se apoya es la de `identificador`? Devuelve (coincide, identificado, mensaje)."""
    propias = [p for ident, p in almacen.todas() if ident == identificador]
    if not propias:
        return False, '', 'La persona no tiene huella enrolada en este lector.'
    for intento in range(1, INTENTOS_VERIFICACION + 1):
        avisar(intento, 'Apoya el dedo en el lector' if intento == 1 else 'No coincidió: vuelve a apoyar el mismo dedo')
        try:
            plantilla, _calidad = lector.capturar(15000, CALIDAD_VERIFICACION)
        except SecuGenError as error:
            if error.codigo not in (ERROR_TIME_OUT, ERROR_FEAT_NUMBER):
                raise
            continue
        if any(lector.coinciden(p, plantilla)[0] for p in propias):
            return True, identificador, 'Identidad verificada.'
        for otro, p in almacen.todas():  # ¿es la huella de otra persona enrolada? Es un intento de suplantación.
            if otro != identificador and lector.coinciden(p, plantilla)[0]:
                return False, otro, f'La huella corresponde a otra persona ({otro}).'
        time.sleep(1)
    return False, '', 'La huella no coincide con la de la persona.'


def atender_verificaciones(cfg, lector, almacen):
    """Si SICMA pidió verificar la identidad de alguien en este lector, lo hace. True si atendió una."""
    try:
        trabajo = llamar_sicma(cfg, 'GET', '/accesos/lector/verificaciones/siguiente/')
    except (urllib.error.URLError, TimeoutError, OSError):
        return False
    if not trabajo:
        return False
    print(f'\n=== VERIFICACIÓN de identidad pedida desde SICMA: {trabajo["nombre"]} ({trabajo["identificador"]}) ===')

    def avisar(intento, indicacion):
        print(f'  {indicacion}')
        try:
            llamar_sicma(cfg, 'POST', f'/accesos/lector/verificaciones/{trabajo["id"]}/progreso/',
                         {'intento': intento, 'total_intentos': INTENTOS_VERIFICACION, 'indicacion': indicacion[:120]})
        except (urllib.error.URLError, TimeoutError, OSError):
            pass

    try:
        coincide, identificado, mensaje = verificar_identidad(lector, almacen, trabajo['identificador'], avisar)
    except SecuGenError as error:
        coincide, identificado, mensaje = False, '', f'Falla del lector: {error}'
    try:
        llamar_sicma(cfg, 'POST', f'/accesos/lector/verificaciones/{trabajo["id"]}/resultado/',
                     {'coincide': coincide, 'identificado': identificado, 'mensaje': mensaje})
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        print(f'  No se pudo informar el resultado a SICMA: {error}')
    print(f'=== {"VERIFICADA" if coincide else "NO VERIFICADA"}: {mensaje} ===\n')
    return True


def atender_bajas(cfg, almacen):
    """Borra de este PC las huellas de las personas eliminadas en SICMA."""
    while True:
        try:
            orden = llamar_sicma(cfg, 'GET', '/accesos/lector/bajas/siguiente/')
        except (urllib.error.URLError, TimeoutError, OSError):
            return
        if not orden:
            return
        borrada = almacen.eliminar(orden['identificador'])
        if borrada:
            almacen.guardar()
        mensaje = 'Huella borrada del lector.' if borrada else 'No había huella enrolada en este lector.'
        print(f'=== Baja desde SICMA: {orden["nombre"]} ({orden["identificador"]}): {mensaje} ===')
        try:
            llamar_sicma(cfg, 'POST', f'/accesos/lector/bajas/{orden["id"]}/resultado/', {'exito': True, 'mensaje': mensaje})
        except (urllib.error.URLError, TimeoutError, OSError):
            return  # se reintenta en la próxima pasada; borrar dos veces no hace daño


class Envios:
    """Envía los intentos a SICMA. Si SICMA no responde, los guarda y los reintenta después."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.ruta_pendientes = os.path.join(os.path.dirname(cfg['plantillas']), 'pendientes.json')
        self.pendientes = []
        if os.path.exists(self.ruta_pendientes):
            with open(self.ruta_pendientes, encoding='utf-8') as archivo:
                self.pendientes = json.load(archivo)

    def _post(self, intento):
        return llamar_sicma(self.cfg, 'POST', '/accesos/lector/intentos/', intento)

    def _guardar_pendientes(self):
        os.makedirs(os.path.dirname(self.ruta_pendientes), exist_ok=True)
        with open(self.ruta_pendientes, 'w', encoding='utf-8') as archivo:
            json.dump(self.pendientes, archivo)

    def enviar(self, intento):
        """Devuelve la respuesta de SICMA, o None si quedó pendiente."""
        self.reintentar()
        try:
            return self._post(intento)
        except urllib.error.HTTPError as error:
            if error.code in (400, 401):  # credenciales o datos inválidos: reintentar no sirve
                print(f'  SICMA rechazó el intento ({error.code}): {error.read().decode(errors="replace")[:200]}')
                return None
            self.pendientes.append(intento)
        except (urllib.error.URLError, TimeoutError, OSError):
            self.pendientes.append(intento)
        self._guardar_pendientes()
        print(f'  SICMA no responde: el intento queda pendiente ({len(self.pendientes)} en cola).')
        return None

    def reintentar(self):
        enviados = 0
        while self.pendientes:
            try:
                self._post(self.pendientes[0])  # el evento_id evita duplicados en SICMA
            except Exception:
                break
            self.pendientes.pop(0)
            enviados += 1
        if enviados:
            self._guardar_pendientes()
            print(f'  {enviados} intentos pendientes enviados a SICMA.')


def escuchar(cfg, _args):
    if not cfg['punto_id'] or not cfg['clave']:
        sys.exit('Completa punto_id y clave en agente_lector.ini (los entrega SICMA al registrar el lector).')
    almacen = Almacen(cfg['plantillas'])
    envios = Envios(cfg)
    print(f'{len(almacen.identificadores())} personas enroladas. Esperando huellas (Ctrl+C para detener)...')
    with Lector(cfg['dir_sdk']) as lector:
        while True:
            intento = {'evento_id': str(uuid.uuid4()), 'fecha_hora': ahora_iso()}
            try:
                plantilla, _calidad = lector.capturar(ESPERA_DEDO_MS, CALIDAD_VERIFICACION)
            except SecuGenError as error:
                if error.codigo == ERROR_TIME_OUT:
                    envios.reintentar()
                    atender_bajas(cfg, almacen)
                    atender_enrolamiento(cfg, lector, almacen) or atender_verificaciones(cfg, lector, almacen)
                    continue
                if error.codigo == ERROR_FEAT_NUMBER:
                    continue  # dedo mal apoyado: no es un intento
                intento.update(estado='error', motivo=str(error)[:200])
            else:
                # ¿Alguien pidió un enrolamiento justo ahora? Entonces ese dedo era para enrolarse, no para entrar.
                if atender_enrolamiento(cfg, lector, almacen) or atender_verificaciones(cfg, lector, almacen):
                    continue
                mejor = max(
                    ((ident, *lector.coinciden(p, plantilla)) for ident, p in almacen.todas()),
                    key=lambda r: (r[1], r[2]),
                    default=None,
                )
                if mejor and mejor[1]:
                    intento.update(estado='coincide', identificador=mejor[0])
                else:
                    intento.update(estado='sin_coincidencia')
            respuesta = envios.enviar(intento)
            hora = datetime.now().strftime('%H:%M:%S')
            if respuesta:
                persona = respuesta.get('persona') or intento.get('identificador') or 'desconocido'
                print(f'{hora} {respuesta["resultado"].upper()} · {persona} · {respuesta.get("motivo", "")}')
            time.sleep(PAUSA_TRAS_INTENTO_S)


def main():
    parser = argparse.ArgumentParser(description='Agente del lector biométrico de SICMA.')
    parser.add_argument('--config', default=os.path.join(AQUI, 'agente_lector.ini'))
    sub = parser.add_subparsers(dest='comando', required=True)
    sub.add_parser('prueba', help='comprueba el lector')
    p = sub.add_parser('enrolar', help='registra la huella de una persona en este PC')
    p.add_argument('identificador')
    p.add_argument('--reemplazar', action='store_true')
    sub.add_parser('listar', help='identificadores enrolados')
    p = sub.add_parser('eliminar', help='borra las plantillas de una persona')
    p.add_argument('identificador')
    sub.add_parser('escuchar', help='espera huellas y las envía a SICMA')
    args = parser.parse_args()

    cfg = cargar_configuracion(args.config)
    comandos = {'prueba': prueba, 'enrolar': enrolar, 'listar': listar, 'eliminar': eliminar, 'escuchar': escuchar}
    try:
        comandos[args.comando](cfg, args)
    except SecuGenError as error:
        sys.exit(f'Error del lector: {error}')
    except KeyboardInterrupt:
        print('\nAgente detenido.')


if __name__ == '__main__':
    main()
