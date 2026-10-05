# Documentación vigente de SICMA

Revisión de alineación del 5 de octubre de 2026. Se conserva el formato y la ruta de los documentos para mantener sus enlaces. El historial de Git conserva las revisiones anteriores.

## Capacidad y estimaciones

**15 horas semanales por integrante**, tres integrantes y 18 semanas: **810 horas-persona**. El Kanban contiene **36 tarjetas y 720 horas estimadas**, más **90 horas de reserva** dentro del semestre. No son horas ejecutadas ni prueba de cumplimiento del plazo.

| Integrante | Estimación | Reserva | Capacidad |
|---|---:|---:|---:|
| Álvaro | 240 h | 30 h | 270 h |
| Fidel | 252 h | 18 h | 270 h |
| Claudio | 228 h | 42 h | 270 h |
| Total | 720 h | 90 h | 810 h |

Las 20 h de #31 ya están incluidas. La tarjeta está completada, pero su estimación no sustituye las horas reales. Los grupos A1–A8 no se suman nuevamente a las tarjetas. A3 tiene 0 h **adicionales** porque el prototipado está incluido en #7 y en interfaces.

## Archivos actuales

- [SICMA_Plan_del_Proyecto.docx](../Documentación/SICMA_Plan_del_Proyecto.docx)
- [1.5_GuiaEstudiante_Fase 1_Definicion Proyecto APT.docx](../Fase1/Evidencias%20Grupales/1.5_GuiaEstudiante_Fase%201_Definicion%20Proyecto%20APT.docx)
- [1.4_APT122_FormativaFase1.docx](../Fase1/Evidencias%20Grupales/1.4_APT122_FormativaFase1.docx)
- [SICMA_Gestion_de_Stakeholders.docx](../Documentación/SICMA_Gestion_de_Stakeholders.docx)
- [SICMA_Estado_de_Avance.docx](../Documentación/SICMA_Estado_de_Avance.docx)
- [SICMA_RHU_v1.3.docx](../Documentación/SICMA_RHU_v1.3.docx)
- [SICMA_Casos_de_Uso_v2.1.docx](../Documentación/SICMA_Casos_de_Uso_v2.1.docx)
- [SICMA_Diagrama_de_Clases_v1.0.docx](../Documentación/SICMA_Diagrama_de_Clases_v1.0.docx)
- [SICMA_Modelo_de_Base_de_Datos_v1.1.docx](../Documentación/SICMA_Modelo_de_Base_de_Datos_v1.1.docx)
- [SICMA_Diagramas_de_Actividad_v1.1.docx](../Documentación/SICMA_Diagramas_de_Actividad_v1.1.docx)
- [SICMA_Mockups_v1.2.docx](../Documentación/SICMA_Mockups_v1.2.docx)
- [Presentación HTML](../Fase1/Evidencias%20Grupales/Presentación%20Proyecto.html), con 18 semanas y capacidad actualizada.

## Alcance

Web Angular operativa según rol; móvil Ionic de solo consulta; inventario e historial; ESP32-S3/DHT22 para temperatura y humedad; Zabbix para infraestructura; registro de accesos decididos por HID; solicitudes en Forms, calendario compartido y avisos con Power Automate; indicadores en Power BI.

Quedan fuera reservas propias y resolución de solapamientos, permisos físicos administrados en SICMA, salud general de dependencias, adjuntos, exportaciones generales y un dashboard analítico web que duplique Power BI. Se mantienen las exclusiones de QR, auditoría general, respaldo lógico, biometría cruda y actuación física.

La fuente funcional es el archivo de instrucciones de SICMA aportado por el equipo. Los 31 RF de esta revisión sustituyen el catálogo ampliado anterior; CU-01 a CU-21 son la numeración vigente. Las figuras y modelos son diseños, no evidencia de implementación.

## Referencias históricas

`SICMA_RHU.docx` y `SICMA_Casos_de_Uso_v2.docx` son antecedentes; usar RHU_v1.3 y Casos_de_Uso_v2.1 con la revisión de octubre. `sicma_schema.sql` y las guías de API describen un estado técnico anterior y deben contrastarse con las migraciones de #9 y los contratos actuales. No se ha modificado el código para aparentar que el nuevo diseño está implementado.

El archivo `Presentación_Proyecto.pptx` contiene solo un salto de línea y **no es un PowerPoint utilizable**. La presentación disponible es HTML; la versión final sigue pendiente en #79. Las evidencias individuales, actas y registros de conflictos conservan su naturaleza histórica y no se rellenan con hechos supuestos.

## Pendientes de validación

- Vincular S1–S18 a fechas académicas oficiales y distribuir horas por semana y persona (máximo 15 h). Registrar horas reales y ausencias.
- Confirmar el mapeo de key users al rol Jefatura.
- Verificar contrato HID, hardware, cuentas, licencias y conectores Microsoft/Power BI.
- Acordar parámetros no cuantificados por la fuente: bloqueo, política y antigüedad de contraseña, intervalo de lectura y retención posterior.
- Ejecutar migraciones, pruebas e integración; la documentación no acredita esos resultados.

## Tarjetas y esfuerzo

| Tarea | Responsable | Horas |
|---|---|---:|
| [#6](https://github.com/AlvaroGonbri/Capstone/issues/6) Planificación y seguimiento del semestre | Claudio | 14 |
| [#7](https://github.com/AlvaroGonbri/Capstone/issues/7) Alinear requerimientos y diseño con el alcance acordado | Claudio | 24 |
| [#9](https://github.com/AlvaroGonbri/Capstone/issues/9) Alinear modelo de datos y migraciones | Fidel | 20 |
| [#14](https://github.com/AlvaroGonbri/Capstone/issues/14) Plan de pruebas y trazabilidad de requisitos | Claudio | 12 |
| [#17](https://github.com/AlvaroGonbri/Capstone/issues/17) API de identidad, cuentas y seguridad de sesión | Álvaro | 24 |
| [#19](https://github.com/AlvaroGonbri/Capstone/issues/19) Web de autenticación y administración de cuentas | Fidel | 24 |
| [#20](https://github.com/AlvaroGonbri/Capstone/issues/20) Web de gestión e historial de activos | Fidel | 32 |
| [#81](https://github.com/AlvaroGonbri/Capstone/issues/81) API de gestión, clasificación e historial de activos | Álvaro | 28 |
| [#27](https://github.com/AlvaroGonbri/Capstone/issues/27) Validar identidad, roles y gestión de activos | Claudio | 16 |
| [#30](https://github.com/AlvaroGonbri/Capstone/issues/30) API de mediciones, umbrales y alertas ambientales | Álvaro | 36 |
| [#31](https://github.com/AlvaroGonbri/Capstone/issues/31) ESP32-S3 y DHT22: lecturas y envío HTTP | Álvaro | 20 |
| [#33](https://github.com/AlvaroGonbri/Capstone/issues/33) Web de monitoreo, umbrales y alertas ambientales | Fidel | 28 |
| [#41](https://github.com/AlvaroGonbri/Capstone/issues/41) Validar monitoreo ambiental de extremo a extremo | Claudio | 16 |
| [#42](https://github.com/AlvaroGonbri/Capstone/issues/42) Integrar Zabbix: servidores, métricas y eventos | Álvaro | 28 |
| [#45](https://github.com/AlvaroGonbri/Capstone/issues/45) Web de estado y problemas de infraestructura | Fidel | 12 |
| [#46](https://github.com/AlvaroGonbri/Capstone/issues/46) Validar integración y alertas de Zabbix | Claudio | 10 |
| [#51](https://github.com/AlvaroGonbri/Capstone/issues/51) API de registro y consulta de accesos HID | Álvaro | 20 |
| [#52](https://github.com/AlvaroGonbri/Capstone/issues/52) Adaptador del lector HID y contrato de eventos | Álvaro | 20 |
| [#54](https://github.com/AlvaroGonbri/Capstone/issues/54) Web de historial de accesos autorizados y rechazados | Fidel | 12 |
| [#57](https://github.com/AlvaroGonbri/Capstone/issues/57) Validar accesos HID y trazabilidad de eventos | Claudio | 12 |
| [#58](https://github.com/AlvaroGonbri/Capstone/issues/58) API del ciclo de intervenciones y su historial | Álvaro | 28 |
| [#59](https://github.com/AlvaroGonbri/Capstone/issues/59) Web de aprobación, seguimiento y cierre de intervenciones | Fidel | 28 |
| [#85](https://github.com/AlvaroGonbri/Capstone/issues/85) Forms y Power Automate: solicitudes y calendario compartido | Claudio | 24 |
| [#66](https://github.com/AlvaroGonbri/Capstone/issues/66) Validar Forms, calendario y ciclo de intervenciones | Claudio | 20 |
| [#67](https://github.com/AlvaroGonbri/Capstone/issues/67) Correos de alertas y respaldo SMTP de intervenciones | Álvaro | 16 |
| [#68](https://github.com/AlvaroGonbri/Capstone/issues/68) Validar notificaciones, destinatarios y fallos | Claudio | 10 |
| [#69](https://github.com/AlvaroGonbri/Capstone/issues/69) Ionic: autenticación y consultas de solo lectura | Fidel | 32 |
| [#71](https://github.com/AlvaroGonbri/Capstone/issues/71) Validar app móvil de consulta | Claudio | 12 |
| [#72](https://github.com/AlvaroGonbri/Capstone/issues/72) Preparar datos e indicadores para Power BI | Fidel | 20 |
| [#73](https://github.com/AlvaroGonbri/Capstone/issues/73) Dashboards de Power BI para Jefatura y Auditor | Fidel | 20 |
| [#74](https://github.com/AlvaroGonbri/Capstone/issues/74) Validar indicadores y permisos de Power BI | Claudio | 10 |
| [#75](https://github.com/AlvaroGonbri/Capstone/issues/75) Clúster MySQL y conmutación del nodo primario | Fidel | 24 |
| [#76](https://github.com/AlvaroGonbri/Capstone/issues/76) Entorno de evaluación y controles de infraestructura | Álvaro | 20 |
| [#77](https://github.com/AlvaroGonbri/Capstone/issues/77) Aceptación final, seguridad y calidad del sistema | Claudio | 20 |
| [#78](https://github.com/AlvaroGonbri/Capstone/issues/78) Documentación técnica y de gestión de la versión evaluada | Claudio | 16 |
| [#79](https://github.com/AlvaroGonbri/Capstone/issues/79) Demostración y paquete de entrega final | Claudio | 12 |
