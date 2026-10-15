# Manual de usuario · Motor Inteligente de Cobranza para PluriOne

**Dirigido a:** evaluador académico y personal de cobranza autorizado.

**Versión:** 1.1 · actualización documental del 15 de octubre de 2026.

**Referencia:** interfaz y backend locales actuales.

Este manual describe lo disponible hoy. La configuración, importación de la base y despliegue corresponden al responsable técnico; véase [README](../README.md). No hay creación general de clientes/deudas ni importador de cartera en la interfaz.

## 1. Cómo acceder al sistema

1. Solicite al responsable la dirección de la aplicación y confirme que se trata del entorno de demostración.
2. En Docker local, la dirección habitual es `http://localhost:8080`; Vite de desarrollo utiliza `http://localhost:5173` si se configuró ese entorno.
3. Abra la dirección en el navegador. Debe aparecer **Motor Inteligente de Cobranza**, con **Iniciar sesión con Microsoft**.
4. Si aparece que Microsoft Entra ID no está configurado, solicite ayuda técnica. No intente crear un usuario legacy ni modificar configuración para eludir el acceso.

**Las credenciales de prueba se entregan por el canal privado definido por TODO Academy.** No se incluyen en este documento ni en el SQL.

## 2. Login Microsoft

1. Pulse **Iniciar sesión con Microsoft**.
2. Seleccione la cuenta autorizada en la pantalla Microsoft y complete los pasos requeridos por la organización.
3. Espere el regreso y la validación de sesión. El menú mostrará el usuario autenticado.
4. Si no se concede acceso, informe al responsable para revisar autorización y configuración del entorno; no comparta tokens o capturas con secretos.

No existe un formulario de contraseña local. El rótulo **Acceso administrativo** no asigna roles: actualmente no hay permisos internos diferenciados por perfil. El acceso depende de Microsoft Entra y del scope de la aplicación.

## 3. Resumen

Pulse **Resumen** en el menú. Las cinco tarjetas muestran datos globales, sin filtro de periodo:

| Tarjeta | Interpretación |
| --- | --- |
| Deudores activos | Clientes con al menos una deuda de saldo positivo. |
| Saldo vencido | Saldo positivo con vencimiento pasado o estado almacenado En Mora. |
| Clientes con estrategia IA | Clientes distintos con al menos una estrategia guardada, incluso histórica. No es el número de mensajes. |
| Clientes sin evaluar | Segmento No definido o nulo entre los clientes registrados. |
| Recuperación | Porcentaje calculado desde monto original y saldo actual; no atribuye resultados a IA. |

La pantalla carga estos datos al entrar y los vuelve a consultar tras pagos, procesamiento desde la ficha y Evaluar cartera. Si hay error de consulta, no interprete los marcadores como valores financieros. No hay un botón general de refresco del Resumen; puede recargar la página con su sesión válida.

## 4. Operación de Cobranza

1. Abra **Operación de Cobranza**.
2. En **Seleccionar cliente**, escriba un ID entero positivo y pulse **Consultar cliente**. También puede seleccionar una fila de Cartera.
3. Revise el panel **Resultado del análisis**. Contiene la ficha y sus subsecciones desplegables.

Consultar un cliente no genera estrategia ni recalcula riesgo. Si no seleccionó uno, el panel lo indicará. Un cliente liquidado también puede consultarse por ID aunque no aparezca en cartera activa.

## 5. Buscar cliente

1. Abra **Cartera**.
2. En **Buscar cliente**, escriba nombre o apellido parcial, ID o folio como `CL-000001`.
3. Opcionalmente configure **Riesgo**, **Análisis**, **Estado de deuda** y **Orden**.
4. Pulse **Buscar / filtrar** para aplicar; cambiar el selector por sí solo no aplica los filtros.
5. Para quitar filtros, vuelva a los valores **Todos**, vacíe la búsqueda y pulse **Buscar / filtrar**.

La búsqueda por nombre no distingue mayúsculas. Los folios distinguen clientes con nombres iguales. Esta tabla muestra solo clientes con deuda activa: no encontrar uno no demuestra que no esté registrado. El filtro **Pagada** busca clientes con alguna deuda pagada, pero sigue exigiendo que tengan otra obligación activa; los completamente liquidados se consultan por ID en Operación.

## 6. Seleccionar cliente

1. Haga clic en cualquier parte de la fila deseada. Con teclado, enfoque la fila y pulse Enter o espacio.
2. La aplicación llena el ID y se desplaza a **Operación de Cobranza**.
3. Confirme folio y nombre antes de registrar pagos o comunicaciones.
4. Revise el saldo y estado de deuda de la ficha, no solo su posición en la tabla.

La selección muestra la información guardada; no inicia llamadas a Groq ni añade historial.

## 7. Consultar deuda

1. En la ficha, abra **Deudas y registro de pagos**.
2. Revise ID de deuda, monto original, saldo, vencimiento y estado.
3. Una deuda con saldo cero se muestra **Pagada** y no ofrece formulario de pago. Una deuda activa vencida se muestra **En Mora**; una futura o del día, **Pendiente**.
4. Revise **Historial de pagos** para consultar fecha, monto, días de atraso y deuda asociada.

El vencimiento relevante de la ficha es el más antiguo entre las obligaciones activas. Los días se calculan usando la fecha del servidor. Un valor negativo de atraso en un pago indica que se pagó antes del vencimiento; una fecha ausente se muestra con un marcador. El detalle conserva datos históricos aunque no quede saldo activo.

## 8. Calcular riesgo: individual o por cartera

La ficha muestra **Probabilidad de pago a tiempo**, **Score de riesgo** y **Segmento** cuando existen. **Sin calcular** no significa bajo riesgo; **No aplica — sin deuda activa** significa que no hay obligación por priorizar.

| Acción | Qué hace | Dependencias y límites |
| --- | --- | --- |
| **Procesar cliente** en la ficha, sin estrategia previa | Análisis individual: riesgo predictivo local y nueva estrategia generativa. | Usa scikit-learn y Groq; no envía comunicaciones. Si ya hay estrategia, el backend reutiliza la guardada sin nuevo cálculo ni llamada generativa por ese solo hecho. |
| **Regenerar estrategia con IA** | Recalcula riesgo y solicita a Groq una nueva versión de texto. | Requiere Groq; conserva el historial y no comunica automáticamente. |
| **Evaluar cartera** en Cartera | Solo evaluación predictiva por lote de clientes activos pendientes o con evaluación incompleta. | Usa scikit-learn local; **sin Groq, estrategia ni comunicaciones**. Omite evaluaciones completas. |
| Registrar pago | Actualiza riesgo si queda deuda activa. | No regenera la estrategia. Si se liquida todo, riesgo no aplica. |

### Pasos para Evaluar cartera

1. Abra **Cartera**.
2. Para revisar pendientes, seleccione **Análisis → Sin evaluar** y pulse **Buscar / filtrar**. Ese filtro identifica segmentos No definido/nulos; una evaluación parcialmente incompleta también puede ser procesada por el lote.
3. Pulse **Evaluar cartera**. La acción considera todos los activos pendientes, no solo las filas visibles por los filtros. No requiere seleccionar fichas ni configurar Groq.
4. Espere **Evaluando cartera...**. El botón se bloquea para impedir doble clic; no pulse acciones de generación para sustituir esta evaluación.
5. Revise el resultado y los nuevos **Score**, **Segmento** y **Prioridad**. Cartera, Resumen y ficha abierta se refrescan. Si seguía filtrando Sin evaluar, los clientes evaluados desaparecerán de esa vista: quite el filtro y aplique **Orden → Mayor prioridad** para revisar el orden nuevo.
6. Interprete los contadores:

| Contador | Significado |
| --- | --- |
| Activos encontrados | Clientes con deuda de saldo positivo en la lectura inicial. |
| Evaluados | Evaluaciones confirmadas y guardadas en esta ejecución. |
| Ya evaluados omitidos | Tenían evaluación completa; no se recalcularon. |
| No pudieron evaluarse | Fallaron al inferir o guardar; se informa su ID para revisión/reintento. |
| Sin deuda al procesar, si aparece | Dejaron de tener saldo activo entre la lectura y su procesamiento; se omitieron. |

Cada cliente tiene su propia transacción. Si uno falla, solo se revierte ese cliente; los éxitos anteriores permanecen guardados y el lote continúa. Puede reintentar: los evaluados se omitirán. Si se pierde la respuesta, consulte la cartera antes de interpretar el resultado. Si falla el refresco de vista, pulse **Actualizar**; no se repite automáticamente el POST.

La función no modifica pagos, deudas, estrategias ni comunicaciones. El interruptor de envíos reales no afecta al cálculo. El modelo local debe estar disponible; si falta, se muestra error. No hay reevaluación forzada ni caducidad temporal por fecha/versión: “completa” no significa validada con datos nuevos. Véase [Evaluar cartera](EVALUAR_CARTERA.md).

### Cómo interpretar el riesgo

| Segmento | Score |
| --- | --- |
| Bajo riesgo | Menor que 0.33. |
| Riesgo medio | Desde 0.33 y menor que 0.66. |
| Alto riesgo | Desde 0.66. |

Score = 1 − probabilidad estimada de pago a tiempo, redondeado a tres decimales. El Random Forest de scikit-learn utiliza seis features y fue reentrenado con 12,000 historiales sintéticos. El comportamiento previo tiene mayor influencia que el saldo. No hay validación empresarial real, calibración ni certificación para producción; el riesgo requiere revisión humana. El vencimiento actual no es una feature directa y sin historial se usan supuestos.

Los scores precargados de los clientes evaluados de la demo provienen del pipeline real aplicado a datos ficticios; ya no se escriben manualmente. 13 y 14 parten sin evaluar y 15 sin deuda. No se garantiza que registrar un pago reduzca el riesgo. La ruta individual `/ia/calcular-riesgo/{cliente_id}` también existe para integración técnica.

## 9. Generar o regenerar estrategia IA

1. Seleccione un cliente con deuda activa y revise sus datos.
2. Si aparece **Estrategia IA: No generada**, pulse **Procesar cliente** y espere.
3. Si ya hay una estrategia, revise su fecha y texto. Para obtener una nueva, pulse **Regenerar estrategia con IA**.
4. Compruebe que el mensaje respeta saldo, vencimientos y condiciones autorizadas. La IA no tiene facultad para aplicar descuentos, recargos o reestructuraciones.
5. Consulte Historial para confirmar la versión nueva y conservar referencia de las anteriores.

Una estrategia guardada puede mostrar **origen histórico no verificado**; las plantillas del SQL demo pertenecen a esa categoría y no prueban una llamada real a Groq. Puede corresponder a un saldo anterior. Un pago no borra ni actualiza automáticamente ese texto. La API reutiliza la última estrategia cuando se solicita procesamiento sin regeneración y ya existe historial; no hay un botón adicional de reutilización en la ficha actual.

Si Groq no está configurado o falla, aparece un error y no se crea una plantilla de respaldo. Generar una estrategia no envía ninguna comunicación. Sin deuda activa, la ficha no ofrece generación/regeneración.

## 10. Consultar historial

1. Abra **Historial** en el menú.
2. Escriba el **ID del cliente** y pulse **Consultar historial**. El campo no cambia automáticamente al seleccionar otra ficha.
3. Revise folio, fecha, monto al momento del análisis y mensaje, recientes primero.
4. Si no existen registros, la pantalla indica que no hay historial para ese ID.

Este menú contiene estrategias, no pagos ni comunicaciones. Esos historiales se consultan dentro de la ficha en sus desplegables. El monto histórico puede diferir del saldo actual.

## 11. Registrar pago

1. Confirme cliente y deuda en **Deudas y registro de pagos**.
2. En una deuda de saldo positivo, escriba **Monto del pago**: positivo, hasta dos decimales y no mayor que el saldo.
3. Pulse **Registrar pago** una sola vez y espere la confirmación.
4. Verifique saldo, **Historial de pagos**, Resumen y Cartera. Si todavía queda deuda, el riesgo se recalcula; no está garantizado que disminuya.
5. Si liquidó todas las obligaciones, la ficha indica **Sin deuda activa** y el cliente deja la cartera activa. Sus historiales se conservan.

La fecha de pago es la del servidor; el formulario no permite retroactividad ni procesa una transacción bancaria. Si falla el cálculo o la actualización, la transacción se revierte. Si se pierde la respuesta o falla el refresco posterior, vuelva a consultar la ficha y el historial antes de repetir: no hay idempotencia distribuida que impida un segundo pago manual.

## 12. Enviar o registrar comunicación

1. Abra **Contacto y comunicaciones** en la ficha de un cliente con deuda activa.
2. Revise el **Historial de comunicaciones** y el texto de **Mensaje de la comunicación**. Puede editarlo; no lo deje vacío.
3. Seleccione **Canal de comunicación**.
4. Espere la consulta del modo y compruebe **Modo: Simulado** o **Modo: Real**. Para evaluación segura debe ser Simulado.
5. Pulse **Enviar comunicación** una sola vez. En simulación este mismo botón registra, sin enviar al proveedor de mensajería.
6. Lea la confirmación y revise el registro. Pulse **Actualizar estados** si necesita consultar la ficha de nuevo.

Si existe última estrategia, la ficha envía su vínculo aunque el texto se edite o se adapte al canal. Sin estrategia puede redactar un mensaje manual, que queda sin vínculo de IA. La API verifica pertenencia de la estrategia. Sin deuda activa rechaza la comunicación de cobranza aunque se introduzca texto.

Si el modo no puede consultarse, el botón queda bloqueado: recargue o solicite ayuda. Ante error o resultado incierto, revise historial antes de reintentar. No hay envíos automáticos al generar estrategias ni reintentos automáticos del handler.

## 13. Email

1. Seleccione **Email**.
2. Revise el texto completo y el modo.
3. Pulse **Enviar comunicación** y consulte el resultado.

Email conserva el mensaje completo, sin adaptación Groq de canal. En modo real necesita SendGrid configurado y destinatario válido; en demo registra una simulación. **Enviado (aceptado; entrega no confirmada)** significa que SendGrid aceptó la solicitud, no que el cliente recibió o abrió el correo. No hay callback de entrega Email implementado en esta aplicación.

## 14. SMS

1. Seleccione **SMS** y compruebe **Modo: Simulado** en la demo.
2. Revise el mensaje original; al registrar, Groq lo adapta a una versión breve.
3. Consulte el texto finalmente guardado en el historial, que puede diferir del original.

La adaptación busca aproximadamente 120–130 caracteres y aplica un límite de 150, limpieza de formato, normalización GSM-7 básica y recorte por palabras completas. Puede omitir información al resumir y necesita revisión humana. También en simulación requiere Groq disponible; si no hay contenido utilizable, no registra comunicación ni contacta Twilio. El modelo SMS se configura por separado. En modo real necesita Twilio, destino válido y permisos de la cuenta; no habilite ese modo para este recorrido.

## 15. WhatsApp

1. Seleccione **WhatsApp**, revise el mensaje completo y el modo.
2. Pulse **Enviar comunicación** una vez y consulte el historial.
3. Si la prueba real está autorizada por separado, confirme estados mediante **Actualizar estados** y la configuración del proveedor con el responsable.

WhatsApp conserva el mensaje original, sin adaptación breve. El envío real depende de Twilio y de las condiciones Sandbox/Trial o del remitente habilitado. El adaptador ajusta el alias mexicano solo para WhatsApp, sin modificar el teléfono almacenado ni el destino SMS. **Leído** solo se muestra cuando Twilio confirma `read` para WhatsApp.

El selector también ofrece **Llamada**: adapta un guion con Groq y registra una simulación. No inicia una llamada telefónica real.

## 16. Significado de modo real y simulado

| Modo | Qué ocurre |
| --- | --- |
| Simulado | Se registra la comunicación, sin petición de envío a Twilio/SendGrid. No demuestra contacto ni recuperación atribuible. SMS/Llamada todavía pueden llamar a Groq para adaptar. |
| Real | Se intenta usar el proveedor configurado. Puede quedar aceptado, pendiente o fallido; no implica entrega automática. |

El modo lo decide el backend según interruptor y configuración, no el usuario mediante un selector. **Real** expresa disponibilidad configurada, no una comprobación de las credenciales con el proveedor. Un fallo de envío real no se convierte en éxito simulado. No modifique el interruptor para resolver un error durante la evaluación.

## 17. Significado de Enviado, Entregado y Fallido

| Estado visible | Interpretación |
| --- | --- |
| Simulado | Registro sin envío externo. |
| Pendiente | Intención real persistida antes de completar la llamada al proveedor; no prueba aceptación. |
| Aceptado por proveedor | Solicitud aceptada, sin entrega confirmada. |
| En cola / Enviando | Progreso informado por Twilio, sin recepción confirmada. |
| Enviado | Aceptación o progreso; entrega todavía no confirmada. |
| Entregado | Twilio notificó `delivered`. |
| Leído | Twilio notificó `read` para WhatsApp. |
| Fallido / No entregado | Rechazo o fallo del proveedor; revisar antes de reintentar. |
| Histórico; entrega no verificada | Registro antiguo sin evidencia suficiente de estado actual. |

Los callbacks deben llegar con firma válida y configuración correcta. Sin esa confirmación puede permanecer un estado de aceptación aunque el proveedor avance. La pantalla no actualiza estados continuamente: use **Actualizar estados**. Ni la bandera interna de éxito ni una respuesta de creación acreditan lectura.

## 18. Cartera priorizada

Abra **Cartera**. Por defecto muestra mayor prioridad primero: **score de riesgo × saldo pendiente**. Puede ordenar por **Mayor saldo**, **Mayor atraso**, **Vencimiento más próximo** o **Nombre**, aplicando **Buscar / filtrar**.

La prioridad es un **índice interno de ordenamiento, no dinero**: combina riesgo estimado e impacto económico. Un saldo mayor puede elevarla aunque el segmento sea medio. Un cliente sin riesgo calculado puede tener prioridad cero: revise el filtro **Sin evaluar** y pulse **Evaluar cartera**, porque cero no significa buen pagador. La acción requiere iniciarse manualmente y revisar los posibles fallos. La tabla muestra deudas activas y permite consultar la ficha; no elige un canal ni ejecuta acciones de cobranza por sí sola. **Actualizar** vuelve a consultar la cartera con los filtros aplicados.

## 19. Analítica IA

1. Abra **Analítica IA**.
2. Espere la carga y revise **Última actualización**.
3. Examine los seis KPIs y las gráficas **Evolución de cartera vencida** y **Recuperación histórica acumulada · MXN**.
4. Pase el puntero por los marcadores para ver fecha y monto; los ejes monetarios usan formato compacto. Abra **Ver fechas y montos** para los valores completos.
5. Revise **Estrategias IA / pagos posteriores** y **Efectividad por canal**. Si la tabla excede el ancho, desplácela horizontalmente.
6. Pulse **Actualizar datos** después de pagos o comunicaciones; esas acciones no refrescan automáticamente este módulo.

Las gráficas usan fechas en X e importes MXN en Y, con línea y marcadores. Un solo registro aparece como punto; no se inventa una tendencia. Sin valores válidos, aparece **Sin datos suficientes para graficar**.

Consultar evolución crea o actualiza el snapshot del día en la base conectada. En operación solo existen capturas de días consultados, sin reconstrucción del pasado ni tarea automática diaria. El dump demo contiene snapshots históricos expresamente inventados para ilustrar las gráficas.

## 20. Filtros de 30, 90, 180 y 365 días

1. En **Periodo**, elija **30 días**, **90 días**, **180 días** o **1 año** (365 días).
2. El cambio vuelve a consultar los datos; el periodo incluye hoy y los días anteriores correspondientes.
3. Use **Actualizar datos** para consultar otra vez el mismo periodo.

Pagos, estrategias y comunicaciones se filtran por periodo. Saldo vencido y riesgo muestran el estado **actual**, no el del inicio del intervalo. La gráfica de recuperación muestra acumulados históricos de los snapshots visibles, no solo pagos del periodo. Las fechas fijas de la demo pueden quedar fuera de 30 días en una presentación posterior: pruebe un periodo mayor y solicite al responsable una regeneración aislada si corresponde.

## 21. Interpretación de KPIs

| KPI de Analítica IA | Definición |
| --- | --- |
| Saldo vencido | Saldo vencido actual con la misma definición del Resumen. |
| Monto recuperado en el período | Suma de pagos positivos, con fecha válida y marcados recuperados dentro del periodo; excluye pagos futuros. |
| Recuperación del período | 100 × pagos del periodo / (pagos del periodo + saldo pendiente actual), cero si no hay denominador. |
| Clientes de alto riesgo | Clientes actualmente activos con score ≥ 0.66; la consulta no recalcula el modelo. |
| Clientes con estrategia IA | Clientes distintos con estrategia en el periodo, no el número de versiones. |
| Recuperación asociada a IA | Pagos elegibles asociados temporalmente a un contacto con estrategia; no prueba causalidad. |

**Recuperación de Resumen y Recuperación del período no son intercambiables.** Resumen usa 100 × (monto original − saldo) / monto original. Por ejemplo, con original 10,000, saldo 6,000 y pagos del periodo 1,000, Resumen indica 40% y Analítica 14.29%. Son fórmulas diferentes, no necesariamente un error.

El bloque IA compara clientes con estrategia, contactados elegibles y con pago posterior. No siempre son una única cohorte. La tasa usa clientes con pago asociado a contactos del periodo divididos por clientes contactados IA del periodo. La tabla por canal distingue enviados aceptados, entregados confirmados, fallidos, simulados, clientes únicos, pagos asociados y monto. No recomienda el mejor canal ni demuestra su superioridad causal.

## 22. Recuperación asociada a IA

Se trata de **recuperación asociada temporalmente a IA**, no causada o garantizada por IA.

Para asociar un pago, debe existir comunicación elegible del mismo cliente por Email, SMS o WhatsApp, ligada explícitamente a estrategia. Debe ser no simulada, exitosa según el registro y sin fallo conocido. La aceptación del proveedor basta para ser candidata; no acredita entrega. El pago debe ocurrir entre uno y siete días después por defecto, según la ventana configurada que muestra la pantalla.

Se excluyen comunicaciones simuladas y pagos del mismo día, porque las fechas no permiten establecer el orden intradía. Si hay varios contactos elegibles, se asigna al más reciente y cada pago se cuenta una sola vez. El contacto puede anteceder al inicio del periodo dentro de la ventana; por ello los contadores no siempre corresponden a una misma cohorte.

En la base demo todas las comunicaciones son simuladas: es correcto ver **cero envíos reales y cero recuperación asociada a IA**, incluso si existen estrategias, pagos y snapshots. No cambie a real para aumentar este indicador. No hay experimento de control ni evidencia causal en el sistema.

## 23. Cerrar sesión

1. Pulse **Cerrar sesión** en el menú.
2. Espere la redirección Microsoft y el regreso a la pantalla de acceso.
3. En un equipo compartido, cierre también la sesión del entorno que corresponda y el navegador según sus políticas.

La aplicación desmonta la información sensible al salir y revalida al retornar. El logout no garantiza revocación instantánea de todos los access tokens previamente emitidos; no comparta una sesión abierta.

## Demostración segura

Solicite al responsable técnico mantener:

```text
COMMUNICATIONS_REAL_ENABLED=false
```

Esta es una configuración del backend, no un control del formulario. Para evaluación sin envíos reales:

1. Use exclusivamente una base demo separada restaurada desde [db/base-de-datos.sql](../db/base-de-datos.sql), nunca cartera operativa.
2. Consulte ID 1 para una ficha con estrategia histórica, ID 13 o 14 para un cliente sin evaluar y ID 15 para uno liquidado. Son referencias del conjunto demo original; pagos o generaciones posteriores pueden cambiar los estados.
3. Revise Resumen, Cartera, historiales y Analítica antes de cambiar datos. El SQL original contiene 15 clientes, 23 deudas, 40 pagos, 24 estrategias, 24 simulaciones y 15 snapshots, con fecha base 2026-10-06.
4. Pulse **Evaluar cartera** para probar 13 y 14 sin Groq: sobre la copia verificada hubo 14 activos, 2 evaluados, 12 omitidos y 0 fallidos. El 13 quedó con probabilidad .720, score .280, Bajo riesgo y prioridad 5208.00; el 14 con .953, .047, Bajo riesgo y 697.95. El 15 sigue sin deuda ni score.
5. Confirme **Modo: Simulado** antes de cada registro. Email/WhatsApp con texto guardado permiten recorrer comunicaciones sin adaptación Groq; generar/regenerar o usar SMS/Llamada sí puede llamar a Groq.
6. Use un pago parcial pequeño que no exceda el saldo y revise el historial; esto modifica únicamente la base demo. Para repetir el estado inicial, pida una nueva base vacía al responsable, sin borrar ni sobrescribir datos operativos.
7. Consulte Analítica y pulse **Actualizar datos**. Espere asociación IA cero porque las comunicaciones son simuladas.
8. Cierre sesión al terminar.

Los nombres, historiales, estrategias y snapshots son ficticios; los scores de clientes evaluados son inferencias reales del modelo sobre ese historial sintético, no valores manuales; correos usan un dominio reservado no entregable y teléfonos son nulos. La demo no contiene credenciales ni crea usuarios Microsoft. **Las credenciales de prueba se entregan por el canal privado definido por TODO Academy.**

## Problemas frecuentes y límites

| Situación | Acción recomendada |
| --- | --- |
| Cliente sin evaluar o con prioridad 0 | Revise el score y ejecute **Evaluar cartera**; cero por ausencia de cálculo no significa bajo riesgo. |
| Cliente no aparece en Cartera | Quite filtros; si está liquidado, consulte por ID en Operación. |
| Estrategia antigua tras pago | Revise fecha/saldo; regenere explícitamente si necesita texto nuevo y Groq está disponible. |
| Error de IA o de adaptación SMS | No suponga que hubo registro/envío; consulte historial y solicite revisión técnica. No habilite proveedores reales. |
| Pago o comunicación sin confirmación | Vuelva a consultar historial antes de repetir. |
| Modo Consultando o error de modo | Espere o recargue; el formulario bloquea envío hasta conocer la configuración. |
| Enviado sin Entregado | No demuestra recepción; actualice estados y consulte al responsable del proveedor si es una prueba real autorizada. |
| Analítica con pocos puntos | Solo hay snapshots de días consultados; revise periodo y fecha base demo. |
| Métricas distintas entre pantallas | Revise sus definiciones y refresque; Resumen y Analítica tienen fórmulas de recuperación diferentes. |

El sistema no ofrece descuentos, reestructuración, selección predictiva de canal, campañas programadas ni llamadas reales. El modelo sintético y los mensajes IA apoyan la revisión humana, sin garantía de recuperación o precisión empresarial.

## Referencias

[PRD](PRD.md), [MVP](MVP.md), [README](../README.md), [Arquitectura](ARQUITECTURA.md), [Analítica IA](ANALITICA_IA.md), [Seguridad](SEGURIDAD.md), [Modelo ML](MODELO_ML.md), [QA](QA.md) y [Auditoría](AUDITORIA_MVP.md). Se describe el código actual: las notas históricas de QA sobre invalidación de estrategias tras pagos no implican regeneración automática. Las pruebas de integración simuladas no certifican el login del tenant ni la entrega real.
