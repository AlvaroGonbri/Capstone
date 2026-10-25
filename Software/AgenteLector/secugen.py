"""Puente mínimo con el FDx SDK Pro de SecuGen (sgfplib.dll, 64 bits) usando ctypes.

Solo lo que el agente necesita: abrir el lector, capturar, crear la plantilla y comparar.
Las firmas salen de `Inc/sgfplib.h` del SDK (v4.3.1). El SDK no se incluye en el repositorio:
se descarga gratis desde secugen.com y su carpeta `bin/x64` se indica en la configuración.
"""
import ctypes
import os
from ctypes import POINTER, Structure, byref, c_ubyte, c_ulong, c_ushort, c_void_p, wintypes

SG_DEV_AUTO = 0xFF
SG_DEV_FDU03 = 0x04  # Hamster Plus (SDU03P)
USB_AUTO_DETECT = 0x3BC + 1
SL_NORMAL = 5
TEMPLATE_FORMAT_ANSI378 = 0x0100

ERROR_NONE = 0
ERROR_TIME_OUT = 54
ERROR_DEVICE_NOT_FOUND = 55
ERROR_DEV_ALREADY_OPEN = 59
ERROR_FAKE_FINGER = 62
ERROR_FEAT_NUMBER = 101

MENSAJES = {
    ERROR_TIME_OUT: 'no se detectó un dedo a tiempo',
    ERROR_DEVICE_NOT_FOUND: 'no se encontró el lector (¿está conectado?)',
    ERROR_DEV_ALREADY_OPEN: 'el lector está abierto por otro programa',
    ERROR_FAKE_FINGER: 'dedo falso detectado',
    ERROR_FEAT_NUMBER: 'la huella tiene muy pocos puntos; vuelve a apoyar el dedo',
    5: 'no se pudo cargar una biblioteca del SDK',
    6: 'no se pudo cargar el driver del lector',
    7: 'no se pudo cargar el algoritmo del SDK',
}


class SecuGenError(Exception):
    def __init__(self, funcion, codigo):
        self.codigo = codigo
        super().__init__(f'{funcion}: {MENSAJES.get(codigo, f"error {codigo} del SDK")}')


class SGDeviceInfoParam(Structure):
    _fields_ = [
        ('DeviceID', c_ulong),
        ('DeviceSN', c_ubyte * 16),
        ('ComPort', c_ulong),
        ('ComSpeed', c_ulong),
        ('ImageWidth', c_ulong),
        ('ImageHeight', c_ulong),
        ('Contrast', c_ulong),
        ('Brightness', c_ulong),
        ('Gain', c_ulong),
        ('ImageDPI', c_ulong),
        ('FWVersion', c_ulong),
    ]


class Lector:
    """Un lector abierto. Usar con `with Lector(dir_sdk) as lector:`."""

    def __init__(self, dir_sdk):
        dll = os.path.join(dir_sdk, 'sgfplib.dll')
        if not os.path.isfile(dll):
            raise FileNotFoundError(f'No está {dll}. Revisa "dir_sdk" en la configuración (carpeta bin\\x64 del SDK).')
        # sgfplib.dll carga sus bibliotecas hermanas (driver y algoritmo) por nombre con LoadLibrary,
        # que busca en el PATH y no en os.add_dll_directory: la carpeta del SDK va en ambos.
        self._dirs = os.add_dll_directory(dir_sdk)
        if dir_sdk not in os.environ.get('PATH', ''):
            os.environ['PATH'] = dir_sdk + os.pathsep + os.environ.get('PATH', '')
        self._sdk = ctypes.WinDLL(dll)
        self._declarar()
        self._h = c_void_p()
        self.ancho = self.alto = self.dpi = 0
        self.serie = ''

    def _declarar(self):
        dword, h, buf = wintypes.DWORD, c_void_p, POINTER(c_ubyte)
        firmas = {
            'SGFPM_Create': [POINTER(c_void_p)],
            'SGFPM_Terminate': [h],
            'SGFPM_Init': [h, dword],
            'SGFPM_SetTemplateFormat': [h, c_ushort],
            'SGFPM_OpenDevice': [h, dword],
            'SGFPM_CloseDevice': [h],
            'SGFPM_GetDeviceInfo': [h, POINTER(SGDeviceInfoParam)],
            'SGFPM_GetImageEx': [h, buf, dword, c_void_p, dword],
            'SGFPM_GetImageQuality': [h, dword, dword, buf, POINTER(dword)],
            'SGFPM_GetMaxTemplateSize': [h, POINTER(dword)],
            'SGFPM_CreateTemplate': [h, c_void_p, buf, buf],
            'SGFPM_GetTemplateSize': [h, buf, POINTER(dword)],
            'SGFPM_MatchTemplate': [h, buf, buf, dword, POINTER(wintypes.BOOL)],
            'SGFPM_GetMatchingScore': [h, buf, buf, POINTER(dword)],
        }
        for nombre, args in firmas.items():
            funcion = getattr(self._sdk, nombre)
            funcion.argtypes = args
            funcion.restype = dword

    def _llamar(self, nombre, *args):
        codigo = getattr(self._sdk, nombre)(*args)
        if codigo != ERROR_NONE:
            raise SecuGenError(nombre, codigo)

    def __enter__(self):
        self._llamar('SGFPM_Create', byref(self._h))
        try:
            # La detección automática a veces falla (p. ej. tras cambiar el lector de puerto USB) aunque
            # el modelo concreto sí inicializa: se intenta automático y luego Hamster Plus.
            codigo = self._sdk.SGFPM_Init(self._h, SG_DEV_AUTO)
            if codigo != ERROR_NONE:
                self._llamar('SGFPM_Init', self._h, SG_DEV_FDU03)
            self._llamar('SGFPM_SetTemplateFormat', self._h, TEMPLATE_FORMAT_ANSI378)
            self._llamar('SGFPM_OpenDevice', self._h, USB_AUTO_DETECT)
            info = SGDeviceInfoParam()
            self._llamar('SGFPM_GetDeviceInfo', self._h, byref(info))
            self.ancho, self.alto, self.dpi = info.ImageWidth, info.ImageHeight, info.ImageDPI
            self.serie = bytes(info.DeviceSN).split(b'\0', 1)[0].decode('ascii', 'replace').strip()
            tamano = wintypes.DWORD()
            self._llamar('SGFPM_GetMaxTemplateSize', self._h, byref(tamano))
            self._max_plantilla = tamano.value
        except Exception:
            self._sdk.SGFPM_Terminate(self._h)
            raise
        return self

    def __exit__(self, *_):
        self._sdk.SGFPM_CloseDevice(self._h)
        self._sdk.SGFPM_Terminate(self._h)
        self._dirs.close()

    def capturar(self, espera_ms=10000, calidad_minima=50):
        """Espera un dedo y devuelve (plantilla, calidad). Lanza SecuGenError con ERROR_TIME_OUT si no llega."""
        imagen = (c_ubyte * (self.ancho * self.alto))()
        self._llamar('SGFPM_GetImageEx', self._h, imagen, espera_ms, None, calidad_minima)
        calidad = wintypes.DWORD()
        self._llamar('SGFPM_GetImageQuality', self._h, self.ancho, self.alto, imagen, byref(calidad))
        plantilla = (c_ubyte * self._max_plantilla)()
        self._llamar('SGFPM_CreateTemplate', self._h, None, imagen, plantilla)
        tamano = wintypes.DWORD()
        self._llamar('SGFPM_GetTemplateSize', self._h, plantilla, byref(tamano))
        return bytes(plantilla[:tamano.value]), calidad.value

    def coinciden(self, plantilla1, plantilla2, nivel=SL_NORMAL):
        """(coinciden, puntaje) entre dos plantillas ANSI 378."""
        a = (c_ubyte * len(plantilla1)).from_buffer_copy(plantilla1)
        b = (c_ubyte * len(plantilla2)).from_buffer_copy(plantilla2)
        resultado, puntaje = wintypes.BOOL(), wintypes.DWORD()
        self._llamar('SGFPM_MatchTemplate', self._h, a, b, nivel, byref(resultado))
        self._llamar('SGFPM_GetMatchingScore', self._h, a, b, byref(puntaje))
        return bool(resultado.value), puntaje.value
