/** Nombre legible y color de cada rol, iguales en toda la app (menú, Usuarios). */
const ROLES: Record<string, { etiqueta: string; corta: string; clase: string }> = {
  administradorprivilegiado: { etiqueta: 'Administrador privilegiado', corta: 'Adm. privilegiado', clase: 'privilegiado' },
  administrador: { etiqueta: 'Administrador', corta: 'Administrador', clase: 'administrador' },
  jefatura: { etiqueta: 'Jefatura', corta: 'Jefatura', clase: 'jefatura' },
  tecnico: { etiqueta: 'Técnico', corta: 'Técnico', clase: 'tecnico' },
  auditor: { etiqueta: 'Auditor', corta: 'Auditor', clase: 'auditor' },
  contratistas: { etiqueta: 'Contratistas', corta: 'Contratistas', clase: 'contratistas' },
};

/** Acepta el rol de la sesión ('administradorprivilegiado') o el de gestión ('AdministradorPrivilegiado'). */
function buscar(rol: string | null | undefined) {
  return rol ? ROLES[rol.toLowerCase()] : undefined;
}

export function etiquetaRol(rol: string | null | undefined, corta = false): string {
  const datos = buscar(rol);
  if (!datos) return rol || 'Sin rol';
  return corta ? datos.corta : datos.etiqueta;
}

/** Clase CSS del chip del rol (definida en styles.scss). */
export function claseRol(rol: string | null | undefined): string {
  return `chip-rol chip-rol--${buscar(rol)?.clase ?? 'sin-rol'}`;
}
