# SICMA · Historial de cambios de la documentación

Autor de todas las versiones: Fidel Rodríguez. Este archivo se actualiza con cada versión nueva. En la carpeta solo se guarda la última versión de cada documento; las anteriores van a la subcarpeta `_para_borrar`.

Última actualización: 2026-10-10.

## Versiones vigentes

| Documento | Archivo | Versión | Fecha |
|---|---|---|---|
| SICMA-REQ Requerimientos | SICMA_REQ_v0.4.docx | 0.4 | 2026-10-10 |
| SICMA-CUS Casos de uso | SICMA_CUS_v0.3.docx | 0.3 | 2026-10-10 |
| SICMA-CLA Diagrama de clases | SICMA_CLA_v0.3.docx | 0.3 | 2026-10-10 |
| SICMA-ACT Diagramas de actividad | SICMA_ACT_v0.3.docx | 0.3 | 2026-10-10 |
| SICMA-BDD Base de datos | SICMA_BDD_v0.3.docx | 0.3 | 2026-10-10 |
| SICMA-MCK Mockups | SICMA_MCK_v0.2.docx | 0.2 | 2026-10-10 |
| SICMA-PLP Plan de pruebas | SICMA_PLP_v0.3.docx | 0.3 | 2026-10-10 |
| SICMA-CPR Casos de prueba | SICMA_CPR_v0.3.docx | 0.3 | 2026-10-10 |

## Decisiones de negocio que generaron cambios

| Fecha | Decisión | Documentos afectados |
|---|---|---|
| 2026-10-10 | Las intervenciones las aprueba la Jefatura y al técnico lo asigna el Administrador. El key user deja de aprobar y de asignar. | REQ 0.3, CUS 0.2, CLA 0.2, ACT 0.2, MCK 0.1 |
| 2026-10-10 | La Jefatura aprueba por Microsoft Teams, con un flujo de Power Automate que entrega la decisión a SICMA. Se cierra D-01. | REQ 0.4, CUS 0.3, CLA 0.3, ACT 0.3, BDD 0.2, MCK 0.2 |
| 2026-10-10 | Las pruebas las hace Claudio Varas como responsable, pero en la práctica los tres. Se siguen la carta Gantt y el plan de trabajo de la Fase 1 (pruebas continuas de la S6 a la S16, semana actual S11). | PLP 0.2 |
| 2026-10-10 | Corrección: la semana en curso es la S9, porque la S1 empieza el 10 de agosto (coincide con Notion). Se rehace el calendario de pruebas en tres ciclos. | PLP 0.3 |
| 2026-10-10 | Las validaciones de rango y unicidad de la base (RI-09 y D-32) las hace el backend, sin CHECK ni únicos en la base. | BDD 0.3 |

## SICMA-REQ · Requerimientos

| Versión | Fecha | Cambios |
|---|---|---|
| 0.1 | 2026-10-09 | Borrador inicial con 36 RF, 20 RNF y 21 historias de usuario. |
| 0.2 | 2026-10-09 | Se agregan matriz de permisos, reglas de negocio, valores de referencia de los RNF y criterios globales de aceptación, tomados de la documentación de la Fase 1. Se aclara que el problema es real y las pruebas son simuladas. |
| 0.3 | 2026-10-10 | La Jefatura aprueba las intervenciones y el Administrador asigna al Técnico. El key user deja de aprobar y asignar. Se ajustan roles, RF-INT-03, HU-15, HU-16, D-01 y glosario. Se agrega la fila "Asignar técnico a la intervención" a la matriz de permisos. Se cierra D-14 y se agrega D-42 (aviso al key user). |
| 0.4 | 2026-10-10 | La Jefatura aprueba por Microsoft Teams con un flujo de Power Automate. Se actualiza RF-INT-03 y se cierra D-01. |

## SICMA-CUS · Casos de uso

| Versión | Fecha | Cambios |
|---|---|---|
| 0.1 | 2026-10-09 | Borrador inicial de actores, diagramas y fichas de casos de uso. |
| 0.2 | 2026-10-10 | La Jefatura aprueba las intervenciones (CU-20) y el Administrador asigna al técnico (CU-21). Se actualizan actores, diagrama del módulo 6, fichas y pendientes (D-01, D-14, D-42). |
| 0.3 | 2026-10-10 | La Jefatura aprueba por Microsoft Teams con un flujo de Power Automate (CU-20). Se actualizan el actor externo, la ficha de CU-20 y el diagrama del módulo 6, y se cierra D-01. |

## SICMA-CLA · Diagrama de clases

| Versión | Fecha | Cambios |
|---|---|---|
| 0.1 | 2026-10-09 | Borrador inicial del modelo de clases. |
| 0.2 | 2026-10-10 | La Jefatura aprueba las intervenciones y el Administrador asigna al Técnico; DecisionIntervencion guarda quién decidió (decididoPor, un usuario). Se cierra D-14 y se reformula D-15. |
| 0.3 | 2026-10-10 | La Jefatura aprueba por Microsoft Teams con Power Automate; el resultado se guarda en DecisionIntervencion. Se cierra D-01. |

## SICMA-ACT · Diagramas de actividad

| Versión | Fecha | Cambios |
|---|---|---|
| 0.1 | 2026-10-09 | Borrador inicial de los diagramas de actividad. |
| 0.2 | 2026-10-10 | AD-08: aprueba la Jefatura. AD-09: asigna el Administrador. Se cierra D-14 y se actualizan los diagramas de ambas actividades. |
| 0.3 | 2026-10-10 | AD-08: la Jefatura aprueba por Microsoft Teams con Power Automate. Se actualiza el diagrama y se cierra D-01. |

## SICMA-BDD · Base de datos

| Versión | Fecha | Cambios |
|---|---|---|
| 0.1 | 2026-10-10 | Borrador inicial del modelo de base de datos. |
| 0.2 | 2026-10-10 | La Jefatura aprueba las intervenciones por Microsoft Teams y quien decide es un usuario de SICMA. Se actualizan D-15 y las referencias a SICMA-REQ v0.4, SICMA-CUS v0.3, SICMA-CLA v0.3 y SICMA-ACT v0.3. |
| 0.3 | 2026-10-10 | RI-09 pasa de No cubierta a Aplicación: el backend valida que el mínimo sea menor que el máximo y que haya un solo umbral vigente. Se cierra D-32. |

## SICMA-MCK · Mockups

| Versión | Fecha | Cambios |
|---|---|---|
| 0.1 | 2026-10-10 | Primera versión. Basada en SICMA-REQ v0.2, SICMA-CUS v0.1, SICMA-CLA v0.1, SICMA-ACT v0.1, SICMA-BDD v0.1 y en el frontend del repositorio del equipo. Las capturas usan nombres ficticios y el frontend solo se usó como referencia de diseño. |
| 0.2 | 2026-10-10 | La Jefatura aprueba por Microsoft Teams: MW-20 muestra la aprobación pendiente en Teams y se cierra D-01. Referencias a SICMA-REQ v0.4, SICMA-CUS v0.3, SICMA-CLA v0.3 y SICMA-ACT v0.3. |

## SICMA-PLP · Plan de pruebas

| Versión | Fecha | Cambios |
|---|---|---|
| 0.1 | 2026-10-10 | Primera versión. Cubre pruebas funcionales, de seguridad, de rendimiento y carga, de integridad de datos y de usabilidad con casos estándar. Basada en SICMA-REQ v0.4, SICMA-CUS v0.3, SICMA-CLA v0.3, SICMA-ACT v0.3, SICMA-BDD v0.3 y SICMA-MCK v0.2, y en la estructura de un plan de pruebas anterior del equipo (solo estructura, sin su contenido). Agrega D-43 a D-48. |
| 0.2 | 2026-10-10 | Las pruebas pasan a ser continuas e incrementales según el plan de trabajo de la Fase 1 (S6 a S16). Calendario por semanas de la carta Gantt, asumiendo que la S11 es del 5 al 11 de octubre de 2026. Claudio Varas es el responsable de las pruebas y en la práctica las ejecutan los tres. Los defectos van a GitHub Issues. Se cierra D-44. |
| 0.3 | 2026-10-10 | Corrige el calendario: la semana en curso es la S9 (la S1 empieza el 10 de agosto). Tres ciclos de pruebas alineados con las fechas de desarrollo de Notion: ciclo 1 en S10 y S11, ciclo 2 en S12 y S13, ciclo 3 en S14 y S15, recuperación del clúster y regresión en la S16, informe final en S17 y S18. D-48 se actualiza. |

## SICMA-CPR · Casos de prueba

| Versión | Fecha | Cambios |
|---|---|---|
| 0.1 | 2026-10-10 | Primera parte: 58 casos de identidad y acceso (25), catálogos (17) y activos (16), con trazabilidad a RF, RNF, CU y reglas de integridad. Agrega D-49 a D-52. Las partes siguientes cubren ambiente, infraestructura, acceso físico, intervenciones, BI, móvil y no funcionales. |
| 0.2 | 2026-10-10 | Segunda parte: 54 casos nuevos de monitoreo ambiental y alertas (26), infraestructura con Zabbix (11) y control de acceso físico (17). Total 112 casos. Incluye los casos de RI-09 validada por el backend. Agrega D-53 a D-59. Por ahora solo se diseñan los casos; los resultados se registran cuando las pruebas se ejecuten. |
| 0.3 | 2026-10-10 | Tercera parte: 87 casos nuevos. Intervenciones (29), inteligencia de negocio (10), plataformas web y móvil (11), rendimiento y carga (7), recuperación del clúster (6), seguridad transversal (10), usabilidad y estándares (6), calidad (4), despliegue (3) y aceptación (1). Total 199 casos, con todos los RF y RNF cubiertos. Agrega D-60 a D-65 y la referencia a D-02, D-04, D-05, D-09, D-11, D-12, D-22, D-24 y D-42. Resultados siguen para la fase de ejecución. |
