"""Plantillas de huella guardadas SOLO en este PC, cifradas con la protección de datos de Windows (DPAPI).

SICMA nunca recibe ni guarda huellas (RF-ACC-01): conoce solo el identificador de cada persona.
El archivo cifrado solo lo puede leer la misma cuenta de Windows que lo creó, en este equipo;
copiarlo a otro PC o abrirlo con otro usuario no sirve.
"""
import base64
import ctypes
import json
import os
from ctypes import POINTER, Structure, byref, c_char, c_void_p, wintypes


class _Blob(Structure):
    _fields_ = [('cbData', wintypes.DWORD), ('pbData', POINTER(c_char))]


_crypt32 = ctypes.WinDLL('crypt32', use_last_error=True)
_kernel32 = ctypes.WinDLL('kernel32')
_crypt32.CryptProtectData.argtypes = [POINTER(_Blob), wintypes.LPCWSTR, c_void_p, c_void_p, c_void_p, wintypes.DWORD, POINTER(_Blob)]
_crypt32.CryptUnprotectData.argtypes = [POINTER(_Blob), c_void_p, c_void_p, c_void_p, c_void_p, wintypes.DWORD, POINTER(_Blob)]
_kernel32.LocalFree.argtypes = [c_void_p]
CRYPTPROTECT_UI_FORBIDDEN = 0x1


def _dpapi(funcion, datos):
    bufer = ctypes.create_string_buffer(datos, len(datos))  # se mantiene vivo durante la llamada
    entrada = _Blob(len(datos), ctypes.cast(bufer, POINTER(c_char)))
    salida = _Blob()
    args = (byref(entrada), 'SICMA plantillas', None, None, None, CRYPTPROTECT_UI_FORBIDDEN, byref(salida))
    if funcion is _crypt32.CryptUnprotectData:
        args = (byref(entrada), None, None, None, None, CRYPTPROTECT_UI_FORBIDDEN, byref(salida))
    if not funcion(*args):
        raise OSError(ctypes.get_last_error() or 'No fue posible cifrar o descifrar las plantillas.')
    try:
        return ctypes.string_at(salida.pbData, salida.cbData)
    finally:
        _kernel32.LocalFree(salida.pbData)


class Almacen:
    """{identificador: [plantilla, ...]} en un archivo cifrado."""

    def __init__(self, ruta):
        self.ruta = ruta
        self._datos = {}
        if os.path.exists(ruta):
            with open(ruta, 'rb') as archivo:
                crudo = json.loads(_dpapi(_crypt32.CryptUnprotectData, archivo.read()))
            self._datos = {k: [base64.b64decode(p) for p in v] for k, v in crudo.items()}

    def guardar(self):
        os.makedirs(os.path.dirname(self.ruta), exist_ok=True)
        crudo = json.dumps({k: [base64.b64encode(p).decode() for p in v] for k, v in self._datos.items()}).encode()
        temporal = self.ruta + '.tmp'
        with open(temporal, 'wb') as archivo:
            archivo.write(_dpapi(_crypt32.CryptProtectData, crudo))
        os.replace(temporal, self.ruta)  # nunca queda un archivo a medio escribir

    def identificadores(self):
        return sorted(self._datos)

    def todas(self):
        for identificador, plantillas in self._datos.items():
            for plantilla in plantillas:
                yield identificador, plantilla

    def agregar(self, identificador, plantillas):
        self._datos[identificador] = list(plantillas)

    def eliminar(self, identificador):
        return self._datos.pop(identificador, None) is not None
