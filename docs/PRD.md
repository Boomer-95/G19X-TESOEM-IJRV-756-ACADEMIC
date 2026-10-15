# Product Requirements Document (PRD)

**Producto:** Motor Inteligente de Cobranza para PluriOne

**Versión documental:** 1.0 · 6 de octubre de 2026

**Referencia de alcance:** implementación local actual y MVP académico v1.

**Estado:** especificación de las capacidades existentes y su aceptación; no certificación de producción.

## 1. Nombre del producto

Motor Inteligente de Cobranza para PluriOne.

## 2. Descripción general

Aplicación web empresarial para consultar cartera, estudiar comportamiento histórico de pago, estimar riesgo, priorizar clientes, registrar pagos y preparar estrategias de recuperación asistidas por IA. Permite registrar comunicaciones simuladas o utilizar proveedores opcionales y consultar analítica operativa.

La visión original comprende análisis de cartera, riesgo financiero, modelos predictivos, automatización de comunicaciones, estrategias de recuperación, visibilidad analítica y estudio de efectividad de canales. El alcance implementado combina consultas y acciones iniciadas por el usuario. La automatización actual adapta mensajes, coordina solicitudes a proveedores y procesa callbacks; no selecciona automáticamente destinatarios, canales ni calendarios de campañas.

FastAPI y SQLAlchemy acceden a PostgreSQL; React/Vite y Recharts presentan la información. Microsoft Entra ID autentica, scikit-learn estima riesgo localmente y Groq redacta estrategias y adaptaciones. Twilio y SendGrid son opcionales. Docker empaqueta la aplicación y GitHub Actions define verificaciones de CI. Azure Machine Learning no forma parte del código actual: el modelo implementado es un Random Forest de scikit-learn.

## 3. Problema que resuelve

La gestión de cobranza requiere relacionar saldos, vencimientos, pagos previos, mensajes y seguimiento. Sin una vista integrada, resulta difícil identificar qué clientes atender primero, conservar evidencia de las acciones y distinguir un intento de comunicación de una entrega confirmada.

El producto reduce la dispersión de información y aporta una priorización explicable por su fórmula. Sus estimaciones y mensajes apoyan la revisión humana; no demuestran mejora causal de recuperación ni reemplazan políticas empresariales de cobranza.

## 4. Objetivo general

Ofrecer un flujo integrado de consulta, priorización y seguimiento de cobranza con datos persistentes, riesgo predictivo y asistencia generativa, permitiendo evaluar resultados operativos de forma trazable y segura.

## 5. Objetivos específicos

- Analizar la cartera mediante indicadores globales de deuda, vencimiento, evaluación y riesgo, permitiendo consultar y priorizar posteriormente a cada cliente por nombre, ID o folio, con filtros y ordenamientos.
- Mostrar saldos y vencimientos junto con el historial de pagos.
- Estimar probabilidad de pago a tiempo, score y segmento mediante el modelo local existente.
- Ordenar la atención por score de riesgo multiplicado por saldo pendiente.
- Generar y conservar versiones de estrategias, con revisión del usuario antes de comunicar.
- Registrar pagos parciales o totales y actualizar saldo y riesgo de forma transaccional.
- Registrar comunicaciones por canal, distinguir simulación y estados de proveedor.
- Mostrar evolución por snapshots y recuperación asociada temporalmente a IA, sin atribuir causalidad.
- Entregar una base ficticia reproducible y documentación para evaluación académica.

## 6. Usuarios objetivo

| Perfil de uso | Necesidad |
| --- | --- |
| Personal de cobranza autorizado | Consultar clientes, revisar estrategias, registrar pagos y comunicaciones. |
| Responsable de cartera | Examinar prioridad, saldos, recuperación y seguimiento por canal. |
| Evaluador académico | Recorrer el flujo con datos ficticios y entender alcance y limitaciones. |
| Responsable técnico | Configurar, migrar, desplegar y verificar el entorno. |

Estos son perfiles de uso, no roles implementados. El acceso depende de Entra y del scope delegado; no existe una matriz interna de permisos por perfil.

## 7. Alcance

Incluye autenticación Microsoft, Resumen, Operación de Cobranza, Cartera, Historial y Analítica IA; consulta de clientes/deudas; registro de pagos; scoring y priorización; estrategias versionadas; comunicaciones manuales asistidas; callbacks Twilio; persistencia PostgreSQL y despliegue Docker.

La interfaz opera sobre clientes y deudas existentes. No ofrece altas, edición o eliminación general de clientes/deudas ni importación de cartera desde archivos. El SQL de entrega crea el esquema y datos demo en una base vacía separada; no es una función de importación del dashboard.

## 8. Requisitos funcionales

| ID | Requisito actual | Implementación y condición |
| --- | --- | --- |
| RF-01 | Autenticar y cerrar sesión con Microsoft | React/MSAL y validación Entra de API; sin login local legacy. |
| RF-02 | Mostrar resumen de cartera | Deudores activos, saldo vencido, clientes con estrategia, sin evaluar y recuperación global. |
| RF-03 | Buscar, filtrar y ordenar clientes | Nombre parcial, ID/folio, riesgo, evaluación, estado de deuda y cinco órdenes; cartera limitada a saldo activo. |
| RF-04 | Consultar ficha | Resumen financiero, riesgo disponible, última estrategia, deudas, pagos y comunicaciones. Seleccionar no genera IA. |
| RF-05 | Registrar pagos | Monto positivo, hasta dos decimales y sin sobrepago; fecha del servidor; actualiza saldo, historial y riesgo. |
| RF-06 | Estimar riesgo | Modelo scikit-learn local. API individual, cálculo al generar/regenerar o registrar pagos y acción «Evaluar cartera» para activos pendientes (`POST /api/cartera/evaluar`), sin Groq ni estrategias en el lote. |
| RF-07 | Priorizar cartera | Score × saldo, orden descendente por defecto; sin deuda activa se excluye de cartera. |
| RF-08 | Generar/reutilizar/regenerar estrategia | Groq, conservación de historial y generación nueva explícita; sin plantilla de respaldo ante fallo. |
| RF-09 | Consultar historial de estrategias | Por ID de cliente, con fecha, monto al momento y mensaje, recientes primero. |
| RF-10 | Registrar comunicaciones | Email, SMS, WhatsApp y guion de Llamada; mensaje editable; vínculo opcional con estrategia del mismo cliente. |
| RF-11 | Distinguir modo y resultado | Simulado o real; aceptación, progreso, entrega/lectura Twilio y fallos; entrega SendGrid no confirmada por callback. |
| RF-12 | Consultar disponibilidad de canales | Booleanos de configuración efectiva; no consulta ni certifica credenciales del proveedor. |
| RF-13 | Mostrar analítica | Periodos 30/90/180/365 días; KPIs, dos gráficas lineales, comparación IA/pagos y tabla de canales. |
| RF-14 | Conservar snapshots | Consulta de evolución crea/actualiza el de hoy; fecha única, sin reconstrucción del pasado operativo. |
| RF-15 | Restaurar entrega ficticia | SQL plano con estructura y datos demo, independiente de la base operativa. |

## 9. Requisitos no funcionales

| ID | Requisito | Situación actual y límite |
| --- | --- | --- |
| RNF-01 | Persistencia e integridad | PostgreSQL con claves foráneas, índices y volumen Docker; migración aditiva explícita. |
| RNF-02 | Consistencia de pagos | Transacción y bloqueo Cliente→Deuda en PostgreSQL; rollback si falla actualización/inferencia. Sin idempotencia distribuida. |
| RNF-03 | Uso empresarial | Layout sobrio, navegación por secciones, etiquetas, estados visibles y tablas desplazables; sin certificación formal de accesibilidad. |
| RNF-04 | Adaptación a pantalla | CSS responsive y gráficas con contenedor responsive; revisión E2E de navegador aún necesaria. |
| RNF-05 | Fallos controlados | Mensajes de error seguros; timeouts de proveedores y sin reintentos automáticos de envío. No existe SLA medido. |
| RNF-06 | Mantenibilidad | Servicios separados, modelo/features compartidos, pruebas backend/frontend y workflow CI. |
| RNF-07 | Despliegue reproducible | Docker Compose con PostgreSQL 16, backend y frontend estático Nginx. Configuración externa requerida. |
| RNF-08 | Rendimiento verificable | Consultas adecuadas al MVP; sin paginación ni pruebas de carga que acrediten grandes carteras. Analítica procesa datos del periodo en memoria. |

## 10. Reglas de negocio

1. Deuda activa: saldo pendiente positivo. Pagada: saldo cero. Una deuda positiva con fecha anterior al día actual se muestra En Mora; una futura o del día se muestra Pendiente. El agregado vencido incluye saldo positivo con fecha pasada **o** estatus almacenado En Mora.
2. El vencimiento relevante del cliente es el más antiguo entre sus deudas activas. Fechas y días dependen del servidor.
3. Riesgo: `score = round(1 − probabilidad_pago_a_tiempo, 3)`. Bajo: score < 0.33; medio: 0.33 ≤ score < 0.66; alto: score ≥ 0.66. Sin evaluar se identifica por segmento nulo/No definido, no por asumir que score cero es buen comportamiento.
4. Prioridad: score disponible × saldo pendiente. Un cliente sin cálculo puede tener prioridad cero y requiere atención humana; cero no demuestra ausencia de riesgo.
5. Sin saldo activo no se ejecutan ML ni Groq para cobranza; score/probabilidad no aplican. Liquidar limpia esos valores y excluye al cliente de cartera, conservando historial.
6. El pago se asocia a cliente y deuda, no excede saldo y usa fecha actual. Si quedan obligaciones se recalcula riesgo, sin garantía de que disminuya. No se aceptan pagos retroactivos mediante el formulario/API actual.
7. Una estrategia existente se reutiliza; un pago no la regenera ni la elimina. Puede reflejar un saldo anterior. `regenerar=true` añade una versión nueva.
8. Groq redacta; no calcula el score ni modifica deuda. No hay aplicación automática de descuentos, convenios, recargos o reestructuraciones. El prompt limita hechos financieros, pero requiere revisión humana.
9. Comunicación requiere deuda activa, mensaje no vacío y canal permitido. Si incluye estrategia, esta debe pertenecer al cliente. Editar texto mantiene el vínculo enviado desde la ficha, sin demostrar que el texto sea idéntico al original.
10. Envíos reales requieren interruptor explícito y configuración completa por canal. Simulación guarda `exitoso=false` y no contacta Twilio/SendGrid. SMS y Llamada requieren adaptación Groq incluso en simulación; Llamada siempre permanece simulada.
11. Aceptación no equivale a entrega. Un fallo real no se convierte en éxito simulado. Los estados históricos sin evidencia permanecen sin entrega verificada.
12. Resumen global: recuperación = 100 × (monto original − saldo actual) / monto original, con cero si no hay original. Analítica: recuperación del periodo = 100 × pagos válidos del periodo / (pagos del periodo + saldo actual). No son la misma medida.
13. Analítica usa pagos positivos, recuperados y con fecha dentro del periodo. La recuperación acumulada de snapshots incluye pagos válidos hasta cada captura.
14. Recuperación asociada temporalmente a IA requiere pago del mismo cliente entre 1 y 7 días después de un contacto elegible ligado a estrategia (ventana configurable de 1 a 365 días). Se excluyen simulaciones, mismo día y fallos; elige el contacto elegible más reciente y cuenta cada pago una sola vez. La aceptación no demuestra recepción ni causalidad.
15. Los snapshots operativos se capturan solo en días consultados. Los 15 snapshots del SQL académico son una excepción explícita: datos inventados de demostración, nunca mezclados con operación.

## 11. Integraciones

| Tecnología | Función implementada |
| --- | --- |
| FastAPI / SQLAlchemy | API y acceso al esquema actual. |
| React / Vite / Recharts | Interfaz y gráficas lineales de cartera/recuperación. |
| PostgreSQL | Clientes, deudas, pagos, estrategias, comunicaciones, snapshots y tabla legacy. |
| Microsoft Entra ID / MSAL | Identidad Microsoft y autorización por access token y scope delegado. |
| scikit-learn / pandas / joblib | Features e inferencia del Random Forest local existente. |
| Groq vía SDK compatible OpenAI | Estrategias, SMS y adaptación de guion; modelo SMS configurable separado. |
| Twilio | SMS/WhatsApp opcionales y callbacks firmados; Voice real no implementado. |
| SendGrid | Email opcional; aceptación, sin callback de entrega implementado. |
| Docker / Nginx | Empaquetado, persistencia y proxy del frontend a API. |
| GitHub Actions | Tests, lint, builds y construcción de imágenes; no despliegue automático. |

La presencia de una integración en código no acredita que una cuenta externa esté configurada, disponible o validada en producción.

## 12. Seguridad

Entra es la única autenticación: MSAL usa Authorization Code con PKCE; la API valida firma RS256, emisor, audiencia, tenant, vigencia y scope. La tabla `administradores` es legacy y no permite login. El rótulo “Acceso administrativo” no implica roles internos.

Los callbacks Twilio usan firma del proveedor y controles de correlación, en lugar de Entra. Secretos de proveedores permanecen en backend y no deben publicarse en variables `VITE_*`, logs o SQL. Groq recibe contexto mínimo de cobranza, sin email, teléfono ni secretos; el contexto puede contener nombre y datos financieros, por lo que datos reales requieren autorización y políticas de privacidad.

El entorno demo mantiene `COMMUNICATIONS_REAL_ENABLED=false`. El SQL académico usa nombres ficticios, correos `example.invalid`, teléfonos nulos y campos de proveedor nulos. Los accesos Microsoft se entregan por separado. No hay rate limiting, roles avanzados ni garantía de revocación inmediata de tokens ya emitidos tras logout. TLS, políticas Entra y revisión de dependencias son requisitos antes de uso productivo.

## 13. Métricas de éxito

Son criterios de evaluación, no resultados empresariales alcanzados ni metas numéricas ya medidas.

| Dimensión | Indicador y evaluación propuesta |
| --- | --- |
| Consulta | Completar búsqueda→ficha sobre clientes demo, con filtros consistentes. |
| Integridad | Pagos válidos concilian saldo e historial; sobrepagos y errores no dejan cambios parciales. |
| Trazabilidad | Estrategias conservadas y comunicaciones ligadas al cliente/estrategia correctos. |
| Interpretación | Evaluador distingue simulado/aceptado/entregado y las dos fórmulas de recuperación. |
| Reproducibilidad | SQL se importa en base vacía con conteos documentados y API consultable. |
| Calidad técnica | Verificaciones automatizadas pertinentes pasan; evidencia externa pendiente se identifica. |
| Valor futuro | Medir tiempo de gestión y resultados de recuperación mediante un estudio autorizado; no hay línea base ni mejora causal demostrada actualmente. |

Los contadores del dashboard son métricas operativas, no pruebas de precisión del modelo o retorno económico. Precision/recall/F1/AUC del entrenamiento sintético no acreditan rendimiento en cartera empresarial.

## 14. Criterios de aceptación

| ID | Escenario | Resultado esperado |
| --- | --- | --- |
| CA-01 | Usuario Microsoft autorizado / solicitud sin autorización | Acceso con scope válido; rechazo seguro sin identidad válida. Prueba interactiva del tenant requerida. |
| CA-02 | Buscar por nombre, ID y folio; seleccionar fila | Ficha correcta, sin generación automática ni incremento de historial. |
| CA-03 | Pago parcial, total, sobrepago o fallo ML | Actualización consistente; liquidación sin riesgo aplicable; rechazo/rollback en casos inválidos. |
| CA-04 | Procesar sin estrategia, reutilizar y regenerar | Nueva estrategia con Groq disponible, reutilización sin llamada nueva y nueva versión explícita sin borrar anteriores. |
| CA-05 | Simulación y fallo externo | Simulación sin envío; fallo real conservado como fallo; SMS inválido no produce comunicación. |
| CA-06 | Callback Twilio / Email aceptado | Firma válida puede actualizar estado; inválida se rechaza; aceptación Email no se presenta como entrega. |
| CA-07 | Cambiar periodo y actualizar analítica | Valores según definición, fechas reales consultadas, tooltip MXN y render con pocos puntos; vacío con mensaje claro. |
| CA-08 | Restaurar SQL en base vacía | 15 clientes, 23 deudas, 40 pagos, 24 estrategias, 24 simulaciones, 15 snapshots y administradores vacíos. |
| CA-09 | Revisar entrega | Documentación y SQL sin secretos ni datos personales reales; operación original intacta. |

La evidencia y las pruebas pendientes se detallan en [MVP](MVP.md), [QA](QA.md) y [Auditoría](AUDITORIA_MVP.md). No se presupone que criterios de integración externa ya estén certificados por mocks.

## 15. Limitaciones actuales

Modelo entrenado con datos sintéticos, sin calibración empresarial ni feature directa de vencimiento actual; salida generativa susceptible a hechos incorrectos; dependencia de configuración/planes externos; ausencia de roles internos, paginación, campañas programadas e idempotencia distribuida. Persisten columnas monetarias Float; snapshots usan Numeric. No hay SLA, E2E completo ni certificación de concurrencia/entrega real por las pruebas SQLite. Las dependencias de desarrollo requieren revisión; no se fijan aquí conteos históricos de vulnerabilidades como estado actual. La disponibilidad del modo real no verifica las credenciales con el proveedor.

## 16. Fuera de alcance del MVP v1

Portal del deudor, pasarela de pago, débito automático, alta/edición masiva de cartera, ERP/CRM, BI externo, selección predictiva del canal, campañas desatendidas, descuentos o reestructuraciones automáticas, Voice real, roles avanzados, Azure ML y despliegue productivo certificado.

## 17. Evolución futura

Post-MVP: entrenar y evaluar temporalmente con historial empresarial autorizado; calibrar y supervisar el modelo; investigar recomendación de canal con evidencia adecuada; incorporar ERP/CRM y BI; migrar importes a Numeric con respaldo y compatibilidad; añadir idempotencia, paginación, roles y auditoría de acciones ampliada. Programación diaria de snapshots y campañas requiere implementación nueva. Descuentos y reestructuración solo podrían recomendarse/aplicarse bajo políticas autorizadas, aprobación y trazabilidad. Despliegue productivo requiere TLS, controles de acceso, monitoreo, pruebas de carga/concurrencia y validación de proveedores.

### Referencias y criterio de coherencia

Fuentes: [README](../README.md), [Arquitectura](ARQUITECTURA.md), [Seguridad](SEGURIDAD.md), [Modelo ML](MODELO_ML.md), [Analítica IA](ANALITICA_IA.md), [QA](QA.md), [Auditoría](AUDITORIA_MVP.md), `app/`, `frontend-react/src/`, `docker-compose.yml`, `.github/workflows/ci.yml` y [SQL demo](../db/base-de-datos.sql). Los resultados numéricos de QA/Auditoría corresponden a revisiones históricas, no a una ejecución nueva para este PRD. La mención antigua de QA a “invalidación tras pago” no significa regeneración actual: el código conserva la estrategia y exige regenerar explícitamente. La prohibición de inventar snapshots operativos coexiste con snapshots demo explícitamente ficticios.
