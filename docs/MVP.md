# MVP v1 · Motor Inteligente de Cobranza para PluriOne

**Versión documental:** 1.0 · 6 de octubre de 2026.

**Alcance:** código local actual; demostración académica asistida por un usuario autorizado.

## Problema mínimo que resuelve

Permite decidir a qué cliente con deuda activa atender, consultar su situación, preparar una estrategia, registrar acciones y pagos, y revisar resultados operativos en una misma aplicación. La priorización combina una estimación local de riesgo con saldo; no representa una optimización financiera validada con datos reales.

## Por qué estas funciones forman parte del MVP

Identidad y persistencia permiten operar con información controlada. Búsqueda y ficha evitan atender al cliente equivocado. Deudas y pagos mantienen una base financiera consistente. Scoring y ordenamiento apoyan la prioridad. Estrategias e historial facilitan seguimiento humano. Comunicaciones y sus estados distinguen registro, aceptación y entrega. Analítica aporta visibilidad sobre cartera, pagos y asociación temporal. Docker, CI y el SQL ficticio hacen la entrega verificable y reproducible.

La automatización se limita a cálculos, generación/adaptación, solicitudes a proveedores y callbacks. Cada pago, estrategia o comunicación se inicia por acción del usuario; no hay campañas autónomas.

## Qué incluye MVP v1

| Capacidad | Alcance real |
| --- | --- |
| Microsoft Entra ID | Login/logout Microsoft, API con scope delegado; sin credenciales locales de administradores. |
| Dashboard Resumen | Cinco KPIs globales provenientes de la base. |
| Clientes y cartera | Búsqueda por nombre/ID/folio; filtros de riesgo/evaluación/deuda y ordenamiento; clientes activos. |
| Ficha | Deudas, pagos, contacto, riesgo y última estrategia; selección sin llamar ML/Groq. |
| Pagos | Registro parcial/total con validación, transacción, historial y recálculo de riesgo cuando corresponde. |
| Riesgo predictivo | Random Forest scikit-learn local con seis features; umbrales y prioridad score × saldo. |
| Estrategias IA | Generación Groq, reutilización y regeneración explícita; versiones históricas conservadas. |
| Sugerencia de canal basada en asociación temporal histórica | Regla observacional (`app/services/canal_sugerido.py`) sobre entregas/lecturas, fallos y pagos dentro de la ventana temporal; preselecciona el canal en la ficha manteniendo la elección manual. No es un modelo predictivo de IA ni demuestra causalidad. |
| Comunicaciones | Email, SMS y WhatsApp opcionales; simulación disponible; texto editable y vínculo de estrategia. Llamada solo como guion simulado. |
| Estados de proveedor | Twilio con callbacks firmados; SendGrid con aceptación sin confirmación de entrega. |
| Analítica IA | Periodos 30/90/180/365, KPIs, gráficas lineales responsive, comparación de estrategias/pagos y canales. |
| Snapshots | Captura/actualización del día al consultar evolución; sin backfill operativo. |
| Persistencia | PostgreSQL 16, SQLAlchemy, migración aditiva y volumen Docker. |
| Ejecución y calidad | Docker/Nginx y GitHub Actions con tests, lint y builds, sin despliegue automático. |
| Entrega académica | SQL plano demo y scripts de generación/importación/validación aisladas. |

Existe la acción **Evaluar cartera** (`POST /api/cartera/evaluar`) para scoring local por lote de activos pendientes, sin Groq, estrategias ni comunicaciones. La API individual `/ia/calcular-riesgo/{cliente_id}` se conserva; en la interfaz también se calcula al generar/regenerar o después del pago. Reutilizar una estrategia guardada no solicita una nueva ni recalcula por ese solo hecho.

## Qué no incluye

- Alta/edición/eliminación general de clientes y deudas desde la interfaz, ni carga masiva de cartera.
- Portal del deudor, cobro bancario, pasarela de pago o registro retroactivo de pagos.
- Descuentos, recargos, convenios o reestructuración aplicados automáticamente.
- Modelo predictivo de IA para selección de canal, campañas programadas o envío autónomo.
- Voice real, callback de entrega SendGrid o refresco continuo de estados.
- Modelo entrenado/calibrado con datos empresariales reales o infraestructura Azure Machine Learning.
- Roles internos avanzados, ERP/CRM, BI externo o despliegue productivo certificado.

## Flujo principal del usuario

1. Entrar con una cuenta Microsoft autorizada al entorno de demostración.
2. Consultar Resumen y Cartera; buscar/filtrar y seleccionar una fila o consultar por ID.
3. Revisar ficha, deuda, pagos previos y riesgo disponible.
4. Si falta estrategia, usar **Procesar cliente**; si existe y se necesita actualizar, **Regenerar estrategia con IA**. Revisar el texto y los hechos financieros.
5. Abrir **Contacto y comunicaciones**, elegir canal y comprobar **Modo: Simulado** para la evaluación. Registrar una comunicación, sin repetir automáticamente ante respuesta incierta.
6. Registrar un pago válido en una deuda activa, comprobar saldo/historial y riesgo actualizado. Liquidación elimina al cliente de cartera activa, no su ficha/historial.
7. Consultar Historial por ID y Analítica IA por periodo; pulsar **Actualizar datos** cuando se necesite refrescarla.
8. Cerrar sesión.

La demo puede consultar estrategias históricas sin generar nuevas. Generación/regeneración y adaptación SMS/Llamada necesitan Groq configurado, incluso si los proveedores de envío están deshabilitados.

## Criterios para considerar el MVP funcional

La instalación debe permitir acceso autorizado, consultas consistentes y recorrido de la ficha; rechazar pagos inválidos y conservar atomicidad; producir estrategias válidas cuando Groq está disponible, o informar error sin inventar una; conservar historial; registrar simulaciones sin envío externo; distinguir aceptación/entrega/fallo; renderizar analítica con datos limitados y persistir su snapshot diario consultado.

La base demo debe restaurarse exclusivamente con [db/base-de-datos.sql](../db/base-de-datos.sql) en PostgreSQL vacío y separado: 15 clientes, 23 deudas, 40 pagos, 24 estrategias, 24 comunicaciones simuladas, 15 snapshots y tabla legacy vacía. Todas las comunicaciones demo tienen identificadores y estados de proveedor nulos. Su recuperación atribuida a IA y sus envíos reales son cero.

“Funcional para demostración” no significa integración externa completamente validada ni aptitud productiva. Login del tenant, entrega/callbacks reales, interacción de navegador, persistencia al recrear servicios y concurrencia PostgreSQL requieren evidencia específica adicional. No se exige un envío real para la evaluación segura.

## Tecnologías utilizadas

Python/FastAPI; SQLAlchemy y PostgreSQL 16; React 18, Vite y Recharts; Microsoft Entra ID y MSAL; scikit-learn, pandas y joblib; Groq mediante SDK compatible OpenAI; Twilio para SMS/WhatsApp; SendGrid para Email; Docker Compose y Nginx; GitHub Actions. El frontend Docker compila con Node 20; CI frontend utiliza Node 22 y backend Python 3.12. La configuración del entorno sigue [README](../README.md).

## Funcionalidades verificadas y límites de la evidencia

| Área | Evidencia disponible | Lo que no demuestra |
| --- | --- | --- |
| API, pagos, riesgo, búsqueda e historial | Tests locales con base SQLite aislada, según QA/Auditoría y suites actuales. | Concurrencia y bloqueos PostgreSQL productivos. |
| Entra | Tokens de prueba RSA y discovery/JWKS simulados, validación de claims/scope. | Login real del tenant o experiencia MSAL en navegador. |
| Groq y comunicaciones | Mocks de respuestas, errores, adaptación y estados; QA documenta una muestra aislada de SMS ficticio. | Fidelidad de todas las futuras salidas ni disponibilidad continua. |
| Twilio/SendGrid | Tests de SDK/callbacks y etiquetas; sin necesidad de envíos en la demo. | Entrega real a destinatarios o configuración externa. |
| Frontend/analítica | Tests de componentes/helpers, periodos/API y cero/uno/dos puntos; build local documentado. | E2E visual ni rendimiento de grandes carteras. |
| SQL de entrega | Importación desde cero en PostgreSQL temporal, conteos, relaciones, secuencias y saldos; GET de métricas/clientes/cartera/analítica con HTTP 200. | Autenticación Microsoft: se sustituyó solo en TestClient local; evolución puede actualizar snapshot demo. |
| CI/Docker | Workflow implementado y configuración inspeccionada; auditorías previas documentan verificaciones locales. | Una nueva ejecución remota de Actions, despliegue o recreación de servicios. |

Este documento no ejecuta de nuevo las suites ni certifica las cuentas externas. Los conteos de tests de [QA](QA.md) y [Auditoría](AUDITORIA_MVP.md) son históricos; no deben sumarse ni presentarse como un resultado nuevo. La entrega SQL se generó con PostgreSQL 16.15: se recomienda cliente `psql` actualizado de la misma rama para sus directivas de restauración.

## Limitaciones documentadas

- Modelo sintético, no validado/calibrado con cartera real. Vencimiento actual no es una feature directa; sin historial se usan supuestos.
- Estrategias y SMS requieren revisión humana. Groq puede fallar; no existe fallback local ni aplicación de condiciones financieras.
- Sin saldo activo no hay generación ni comunicación de cobranza; riesgo no aplica.
- Estrategia histórica puede reflejar saldo anterior; se conserva después del pago. La referencia antigua de QA a “invalidación tras pago” no implica regeneración automática actual.
- Resumen global y Analítica usan fórmulas distintas de recuperación; ninguna prueba causalidad de IA.
- Asociación temporal excluye simulaciones, pagos del mismo día y fallos, y admite aceptación sin entrega verificada. La ventana predeterminada es siete días.
- Snapshots capturan días consultados, sin tarea diaria instalada. Los históricos del SQL son ficticios y su fecha base es 2026-10-06; el periodo visible cambia al transcurrir el tiempo.
- Llamada solo simulada; Email sin confirmación de entrega en la aplicación. Estados no tienen polling automático.
- Sin roles internos, rate limiting ni idempotencia distribuida de pagos/envíos. Columnas monetarias Float heredadas, sin paginación y sin SLA o prueba de carga.
- Pendientes de seguridad/dependencias y verificaciones externas recogidos en documentos existentes; no se realizó una auditoría nueva de paquetes aquí.

## MVP v1 frente a Post-MVP

| MVP v1 implementado | Post-MVP propuesto, no implementado |
| --- | --- |
| Priorización score × saldo, sugerencia observacional de canal por asociación temporal histórica y elección final por usuario | Modelo predictivo de IA para selección de canal con validación empresarial y atribución causal. |
| Estrategias revisadas por el usuario y propuestas informativas sujetas a revisión humana | Aplicación automatizada de descuentos y reestructuración con motor de políticas y autorización. |
| Random Forest entrenado con datos sintéticos | Modelos con datos empresariales autorizados, evaluación temporal y calibración. |
| Acceso Entra por scope | Roles avanzados y permisos por operación/cartera. |
| PostgreSQL y consultas propias | ERP/CRM, intercambio controlado de cartera y BI externo. |
| Capturas al consultar y acciones manuales | Programación diaria, campañas con aprobación y supervisión. |
| Docker y CI de verificación | Despliegue productivo con TLS, monitoreo, respaldo y recuperación probada. |

Posibles versiones posteriores: v1.1 para robustez monetaria, idempotencia y rendimiento; v2 para integración empresarial y modelo validado; una fase posterior para recomendaciones autorizadas y automatización supervisada. Son una propuesta de evolución, sin fechas comprometidas ni capacidades disponibles hoy.

## Documentos relacionados

[PRD](PRD.md), [Manual de usuario](MANUAL_USUARIO.md), [README](../README.md), [Arquitectura](ARQUITECTURA.md), [QA](QA.md), [Seguridad](SEGURIDAD.md), [Modelo ML](MODELO_ML.md) y [Analítica IA](ANALITICA_IA.md). El código local prevalece ante descripciones históricas; los documentos anteriores no se modificaron.
