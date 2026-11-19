import { Injectable } from '@angular/core';
import { Capacitor } from '@capacitor/core';
import { BiometryType, NativeBiometric } from '@capgo/capacitor-native-biometric';
import { environment } from '../../../environments/environment';

/** Identificador del registro en el almacén seguro de Android (Keystore). */
const SERVIDOR = 'cl.brionessolutions.sicma';
/** Nombre de la persona que activó la huella en este teléfono ("Entrar como …"). No es secreto. */
const CLAVE_ACTIVA = 'sicma.huella.nombre';

/**
 * Ingreso con huella o PIN del teléfono, solo en la app móvil.
 *
 * La huella nunca sale del teléfono: Android la verifica y entrega la "llave del dispositivo" que la
 * app guardó en el Keystore. SICMA solo recibe esa llave (ver login/dispositivo.py en el backend).
 */
@Injectable({ providedIn: 'root' })
export class BiometriaService {
  /** La web no usa huella: solo la app instalada en el teléfono. */
  readonly soportada = environment.soloConsulta && Capacitor.isNativePlatform();

  /** ¿El teléfono tiene huella, rostro o al menos un PIN/patrón configurado? */
  async disponible(): Promise<boolean> {
    if (!this.soportada) {
      return false;
    }
    try {
      return (await NativeBiometric.isAvailable({ useFallback: true })).isAvailable;
    } catch {
      return false;
    }
  }

  /** Nombre de quien activó la huella en este teléfono, o null si no está activa. */
  activa(): string | null {
    if (!this.soportada) {
      return null;
    }
    try {
      return localStorage.getItem(CLAVE_ACTIVA);
    } catch {
      return null;
    }
  }

  /** Guarda (o reemplaza) la llave en el almacén seguro del teléfono. */
  async guardar(llave: string, nombre: string): Promise<void> {
    await NativeBiometric.setCredentials({ username: nombre, password: llave, server: SERVIDOR });
    try {
      localStorage.setItem(CLAVE_ACTIVA, nombre);
    } catch {
      /* almacenamiento no disponible: la próxima vez se ofrecerá activar de nuevo */
    }
  }

  /** Pide la huella (o el PIN/patrón) y, si coincide, devuelve la llave guardada. */
  async desbloquear(): Promise<string> {
    await NativeBiometric.verifyIdentity({
      title: 'Entrar a SICMA',
      subtitle: 'Usa tu huella o el PIN del teléfono',
      maxAttempts: 5,
      allowedBiometryTypes: [
        BiometryType.FINGERPRINT,
        BiometryType.FACE_AUTHENTICATION,
        BiometryType.IRIS_AUTHENTICATION,
        BiometryType.DEVICE_CREDENTIAL, // PIN, patrón o contraseña del teléfono
      ],
    });
    return (await NativeBiometric.getCredentials({ server: SERVIDOR })).password;
  }

  /** La llave guardada, sin pedir la huella: solo para invalidarla en el servidor al cerrar sesión. */
  async llaveParaInvalidar(): Promise<string | null> {
    if (!this.activa()) {
      return null;
    }
    try {
      return (await NativeBiometric.getCredentials({ server: SERVIDOR })).password;
    } catch {
      return null;
    }
  }

  /** Borra la llave del teléfono: la próxima vez se entra con contraseña. */
  async olvidar(): Promise<void> {
    try {
      localStorage.removeItem(CLAVE_ACTIVA);
    } catch {
      /* almacenamiento no disponible */
    }
    if (this.soportada) {
      await NativeBiometric.deleteCredentials({ server: SERVIDOR }).catch(() => undefined);
    }
  }
}
