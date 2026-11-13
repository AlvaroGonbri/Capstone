import { Component, Input } from '@angular/core';

/**
 * Marco común de las pantallas sin sesión (ingreso y contraseñas):
 * panel de marca a la izquierda y tarjeta con el formulario a la derecha.
 * Solo presentación: el formulario de cada página se proyecta tal cual.
 */
@Component({
  selector: 'app-pantalla-ingreso',
  template: `
    <div class="pantalla">
      <aside class="marca" aria-hidden="true">
        <div class="marca__logo">
          <div class="marca__icono">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="4" y="3" width="16" height="6" rx="1" />
              <rect x="4" y="15" width="16" height="6" rx="1" />
              <path d="M8 6h.01M8 18h.01M12 9v6" />
            </svg>
          </div>
          <div>
            <p class="marca__nombre">SICMA</p>
            <p class="marca__sub">Sistema Integrado de Control y Monitoreo de Activos</p>
          </div>
        </div>
        <h2 class="marca__lema">Control y monitoreo<br />de activos del<br />datacenter.</h2>
        <p class="marca__texto">Inventario, ambiente, servidores, accesos e intervenciones en un solo lugar.</p>
        <ul class="marca__fuentes">
          <li><b>Zabbix</b>servidores</li>
          <li><b>ESP32</b>ambiente</li>
          <li><b>SecuGen</b>accesos</li>
          <li><b>Power BI</b>indicadores</li>
        </ul>
        <svg class="marca__fondo" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="0.6">
          <rect x="4" y="3" width="16" height="6" rx="1" />
          <rect x="4" y="15" width="16" height="6" rx="1" />
          <path d="M8 6h.01M8 18h.01M12 9v6" />
        </svg>
      </aside>

      <main class="contenido">
        <div class="tarjeta">
          <div class="tarjeta__marca-movil">
            <div class="marca__icono">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="4" y="3" width="16" height="6" rx="1" />
                <rect x="4" y="15" width="16" height="6" rx="1" />
                <path d="M8 6h.01M8 18h.01M12 9v6" />
              </svg>
            </div>
            <span>SICMA</span>
          </div>
          <h1 class="tarjeta__titulo">{{ titulo }}</h1>
          @if (subtitulo) {
            <p class="tarjeta__subtitulo">{{ subtitulo }}</p>
          }
          <ng-content></ng-content>
        </div>
      </main>
    </div>
  `,
  styles: `
    :host {
      display: block;
    }
    .pantalla {
      display: flex;
      min-height: 100vh;
      min-height: 100dvh;
    }
    .marca {
      position: relative;
      overflow: hidden;
      width: min(42%, 620px);
      flex-shrink: 0;
      display: flex;
      flex-direction: column;
      padding: 56px;
      background: var(--sicma-consola);
      color: #fff;
    }
    .marca p {
      margin: 0;
    }
    .marca__logo {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .marca__icono {
      width: 44px;
      height: 44px;
      border-radius: 10px;
      background: var(--ion-color-primary);
      color: #fff;
      display: grid;
      place-items: center;
      flex-shrink: 0;
    }
    .marca__icono svg {
      width: 22px;
      height: 22px;
    }
    .marca__nombre {
      font-size: 1.35rem;
      font-weight: 700;
      letter-spacing: 0.06em;
    }
    .marca__sub {
      font-size: 0.72rem;
      color: #7f8e99;
    }
    .marca__lema {
      margin: auto 0 0;
      padding-top: 80px;
      font-size: clamp(2rem, 3vw, 2.6rem);
      line-height: 1.1;
      letter-spacing: -0.03em;
      font-weight: 700;
      position: relative;
    }
    .marca__texto {
      margin-top: 18px !important;
      max-width: 420px;
      color: #9fb0bb;
      font-size: 0.95rem;
      line-height: 1.55;
      position: relative;
    }
    .marca__fuentes {
      list-style: none;
      padding: 0;
      margin: 56px 0 0;
      display: flex;
      flex-wrap: wrap;
      gap: 26px;
      font-size: 0.75rem;
      color: #7f8e99;
      position: relative;
    }
    .marca__fuentes b {
      display: block;
      font-family: var(--sicma-mono);
      font-weight: 500;
      font-size: 1.1rem;
      color: #9fe0e5;
    }
    .marca__fondo {
      position: absolute;
      right: -90px;
      top: 110px;
      width: 420px;
      height: 420px;
      opacity: 0.07;
      color: #fff;
    }
    .contenido {
      flex: 1;
      display: grid;
      place-items: center;
      padding: 32px 20px;
    }
    .tarjeta {
      width: 100%;
      max-width: 420px;
      background: var(--sicma-superficie);
      border: 1px solid var(--sicma-linea);
      border-radius: 12px;
      padding: 32px 32px 26px;
    }
    .tarjeta__marca-movil {
      display: none;
      align-items: center;
      gap: 10px;
      margin-bottom: 22px;
      font-weight: 700;
      letter-spacing: 0.06em;
    }
    .tarjeta__marca-movil .marca__icono {
      width: 34px;
      height: 34px;
      border-radius: 8px;
    }
    .tarjeta__marca-movil .marca__icono svg {
      width: 18px;
      height: 18px;
    }
    .tarjeta__titulo {
      margin: 0;
      font-size: 1.4rem;
      font-weight: 700;
      letter-spacing: -0.01em;
      color: var(--sicma-tinta);
    }
    .tarjeta__subtitulo {
      margin: 4px 0 0;
      font-size: 0.85rem;
      color: var(--sicma-tenue);
    }
    @media (max-width: 899px) {
      .marca {
        display: none;
      }
      .tarjeta__marca-movil {
        display: flex;
      }
      .tarjeta {
        padding: 26px 22px 22px;
      }
    }
  `,
})
export class PantallaIngresoComponent {
  @Input({ required: true }) titulo = '';
  @Input() subtitulo = '';
}
