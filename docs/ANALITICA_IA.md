# Analítica IA · Riesgo, seguimiento y recuperación

## 1. Objetivo del módulo

Analítica IA permite examinar el riesgo de la cartera y el seguimiento de cobranza mediante estrategias, comunicaciones, pagos, saldos y evolución. Integra información para estudiar asociaciones temporales, sin atribuir a la IA una recuperación causada o garantizada.

El módulo complementa el dashboard existente. Conserva Entra, Groq y proveedores. Todos los endpoints requieren el token Entra habitual. Las consultas calculan el estado actual desde la base; el botón **Actualizar datos** vuelve a consultarlas. No usa WebSockets ni refresco automático.

## 2. Arquitectura de IA del proyecto

El proyecto combina un componente predictivo y uno generativo. Analítica IA integra sus resultados con los registros operativos; no es un tercer modelo de inteligencia artificial.

| Componente | Implementación y función | Alcance |
| --- | --- | --- |
| IA predictiva | scikit-learn / Random Forest estima la probabilidad de pago a tiempo; de ella se deriva el score y el segmento de riesgo bajo, medio o alto. | Es el componente predictivo. Fue entrenado con datos sintéticos; no es un modelo empresarial calibrado. |
| IA generativa | Groq redacta estrategias de cobranza y adapta determinados mensajes. | Produce texto para revisión humana. No calcula el score, no modifica deuda ni decide automáticamente descuentos, reestructuraciones o campañas. |
| Analítica IA | Integra y presenta riesgo, estrategias, comunicaciones, pagos, saldos y snapshots. | Permite estudiar evolución y asociaciones temporales; no demuestra causalidad entre IA y recuperación. |

La inferencia predictiva utiliza el modelo de scikit-learn cargado por el backend. Azure Machine Learning no está implementado en esta arquitectura.

## 3. Flujo de análisis de un cliente

El siguiente esquema representa el flujo conceptual de información y seguimiento:

```text
Datos del cliente (historial de pagos y deudas)
→ scikit-learn / Random Forest
→ probabilidad de pago a tiempo
→ score de riesgo
→ segmento de riesgo
→ priorización de cartera (score × saldo pendiente)
→ Groq (generación solicitada por el operador)
→ estrategia de cobranza (texto revisable)
→ comunicación (envío solicitado por el operador)
→ pago / resultado registrado, si ocurre
→ Analítica IA
```

Las flechas no implican una ejecución automática de todas las etapas ni causalidad con el pago. La priorización ayuda a ordenar la atención, pero no dispara por sí sola estrategias o envíos. El operador revisa el mensaje y elige el canal; no existe selección predictiva automática del mejor canal. Analítica IA también consulta saldos y riesgos actuales aunque no haya comunicación ni pago posterior.

## 4. IA predictiva con scikit-learn

El componente predictivo utiliza `RandomForestClassifier`. Extrae seis variables del historial de pagos y las deudas activas: proporción de pagos tardíos, promedio de días de atraso, número de pagos históricos, monto promedio de pago, saldo pendiente actual y número de deudas activas. La probabilidad estimada de pago a tiempo se transforma en riesgo:

```text
score_riesgo = round(1 - probabilidad_pago_a_tiempo, 3)
```

| Segmento | Regla sobre el score |
| --- | --- |
| Bajo riesgo | Menor que 0.33. |
| Riesgo medio | Mayor o igual que 0.33 y menor que 0.66. |
| Alto riesgo | Mayor o igual que 0.66. |

El modelo fue reentrenado con **12,000 historiales sintéticos**. En su test reservado: ROC AUC **.8464**, accuracy **.7558**, precision **.6118**, recall **.8208** y F1 **.7010**, con pago a tiempo como clase positiva. `pct_pagos_tarde` tiene importancia relativa aproximada de **72.33%** y `promedio_dias_atraso` de **22.58%**; el saldo ya no domina el bosque. Importancia de features no significa porcentaje causal del riesgo. Estas métricas son exclusivamente sintéticas; no hay rendimiento validado sobre cartera empresarial real, calibración ni certificación para producción. Sin historial se emplean supuestos para algunas variables, que no representan comportamiento observado. Sin deuda activa no se ejecuta la predicción: score y probabilidad no aplican y el segmento es **Sin deuda**. Analítica IA lee el riesgo almacenado, sin recalcular el modelo. Véase [MODELO_ML.md](MODELO_ML.md) para el detalle del entrenamiento y las variables.

### Evaluar cartera sin generación

En Cartera, **Evaluar cartera** llama a `POST /api/cartera/evaluar`. Solo infiere riesgo local para activos pendientes o con evaluación incompleta, reutilizando `recalcular_riesgo`, y omite evaluaciones completas. Guarda probabilidad, score y segmento del Cliente; no modifica pagos/deudas, no genera estrategias ni comunicaciones, no usa Groq/Twilio/SendGrid ni requiere `GROQ_API_KEY`. Cada cliente tiene su transacción: rollback individual y continuación ante fallo.

Muestra activos, evaluados, omitidos y fallidos; actualiza Cartera, Resumen y ficha abierta. Analítica sigue leyendo los valores persistidos: su botón **Actualizar datos** vuelve a consultarlos y no calcula riesgo. No hay evaluación periódica automática, fecha/versión de vigencia ni reevaluar todos. Ver [Evaluar cartera](EVALUAR_CARTERA.md).

## 5. IA generativa con Groq

Groq recibe contexto del cliente, incluyendo el riesgo calculado, deudas activas e historial reciente, y redacta un mensaje breve, profesional y empático. La estrategia almacenada es ese texto de apoyo a la gestión, no un plan financiero ejecutable. También adapta determinados mensajes, como la versión SMS, con restricciones de formato y fidelidad al original.

Puede reutilizarse una estrategia existente; consultar un cliente no implica generar siempre un texto nuevo. Groq no calcula el score, no modifica deuda ni decide o aplica automáticamente descuentos, reestructuraciones o campañas. Las instrucciones prohíben inventar condiciones financieras, pero el contenido requiere revisión humana.

La ficha envía el identificador de la estrategia utilizada, incluso si se adapta su texto al canal o se edita. La API verifica que la estrategia pertenezca al cliente. Mensajes sin estrategia conservan un identificador nulo.

## 6. Priorización de cartera

La cartera se ordena por defecto de mayor a menor prioridad, combinando el riesgo almacenado y la suma de saldos positivos de las deudas activas del cliente:

```text
prioridad = score de riesgo × saldo pendiente
```

El código calcula `round((score_riesgo or 0) * saldo, 2)`. El resultado es un **índice interno de ordenamiento, no una cantidad monetaria**, una pérdida esperada validada ni una estimación del importe que se recuperará. Por ejemplo, un score de 0.8 y un saldo de 1,000 producen una prioridad de 800, utilizada para comparar posiciones en la cartera.

Un saldo mayor puede elevar la prioridad incluso con riesgo medio. Si falta el score, se utiliza cero: una prioridad cero no demuestra bajo riesgo y requiere revisar si el cliente está sin evaluar. La acción manual **Evaluar cartera** permite calcular esos pendientes sin entrar a cada ficha y evitar que conserven prioridad cero solo por falta de procesamiento individual; requiere ejecutarse y revisar fallos. El ordenamiento apoya la atención humana; no selecciona canales ni ejecuta acciones de cobranza.

## 7. Analítica y KPIs

Los indicadores combinan estado actual de cartera, registros de un periodo y valores capturados en snapshots. El saldo pendiente es actual, mientras que los pagos se delimitan por fecha. Las definiciones completas se conservan en **Periodos y fórmulas**.

Los endpoints `/api/analitica/resumen`, `/api/analitica/evolucion` y `/api/analitica/canales` presentan, respectivamente, indicadores de cartera y seguimiento, evolución mediante snapshots y resultados agrupados por canal. Los clientes con estrategia, contactados y con pago deben interpretarse según sus definiciones; no representan necesariamente una única cohorte.

## 8. Recuperación asociada temporalmente a IA

Un candidato requiere el mismo cliente y `estrategia_id IS NOT NULL`, canal Email, SMS o WhatsApp, envío exitoso, modo distinto de simulado y sin estado de fallo. La aceptación del proveedor no prueba entrega. Se excluyen pendientes, fallidos y simulados; los simulados se muestran por separado. Un registro legacy exitoso puede participar si tiene vínculo explícito; ninguno se rellena automáticamente.

La ventana inicial es **7 días**, configurable con `ANALITICA_VENTANA_IA_DIAS` (entero de 1 a 365; valores enteros fuera de rango se limitan a esos extremos). El pago debe ocurrir entre 1 y 7 días después del envío. Dado que `fecha_envio` y `fecha_pago` son DATE, se excluye el mismo día: no se puede demostrar su orden. Entre varios contactos elegibles se elige el más reciente, desempate por id mayor. Cada pago pertenece como máximo a un contacto y un canal; las sumas por canal coinciden con el total asociado.

Esto es **recuperación asociada temporalmente a una estrategia IA**, no causalidad demostrada. No hay grupo de control, experimento ni ajuste por factores externos. Los clientes con estrategia, contactados y con pagos no siempre forman una misma cohorte; las gráficas muestran sus definiciones y la tasa usa la cohorte contactada.

## 9. Efectividad por canal

La efectividad se examina con indicadores descriptivos de envíos, estados y pagos asociados. Compararlos no demuestra que un canal cause más recuperación ni implica una selección predictiva automática del mejor canal.

Por canal se cuentan envíos aceptados del periodo, entregas con `provider_status=delivered|read`, fallos con estado Fallido o status failed/undelivered/bounced/dropped, simulaciones, clientes únicos y pagos asociados. Los pagos se filtran por su fecha, aunque el contacto elegido pueda ser anterior al periodo. No se presenta Llamada como proveedor implementado.

Email utiliza SendGrid; SMS y WhatsApp utilizan Twilio. Los callbacks firmados de Twilio actualizan estados de comunicaciones existentes. La distinción entre aceptación, entrega, lectura y fallo depende de los estados disponibles del proveedor.

## 10. Snapshots y evolución

`GET /api/analitica/evolucion` crea o actualiza el snapshot de hoy. PostgreSQL usa bloqueo transaccional y upsert sobre fecha única; las consultas concurrentes no generan duplicados. El snapshot del día puede cambiar, los anteriores se conservan. El primer snapshot determina la fecha real de inicio, consultable en `resumen.inicio_historico`. En operación no hay una fecha de inicio preestablecida ni se inventan snapshots pasados. El SQL demo es una excepción explícita: contiene 15 snapshots académicos ficticios con fecha base 2026-10-06, no reconstrucciones operativas. Esta estrategia registra **días con consultas**, no garantiza registros en días sin actividad. Para recopilación diaria continua, un proceso programado autenticado puede consultar evolución cada día.

Los registros de `metricas_snapshots` son capturas de indicadores en una fecha, no nuevos entrenamientos ni reconstrucciones del pasado. Permiten observar cambios entre fechas registradas, con las limitaciones de cobertura y asociación temporal aquí descritas.

## 11. Periodos y fórmulas

Las tres rutas `/api/analitica/resumen`, `/api/analitica/evolucion` y `/api/analitica/canales` aceptan `dias=30|90|180|365` (30 por defecto); otros valores devuelven 422. El periodo incluye hoy y los `dias-1` días anteriores. Se excluyen pagos futuros, pagos sin fecha, montos no positivos y registros con `se_recuperó != true`.

| Métrica | Definición |
| --- | --- |
| Saldo pendiente | Suma actual de saldos de deudas; comparte cálculo con `/api/metricas`. |
| Saldo / cartera vencida | Suma actual de saldos positivos con estatus En Mora o vencimiento anterior a hoy, igual al dashboard existente. |
| Monto recuperado total | Suma de pagos válidos registrados en el periodo; no se infiere restando saldo al monto original. |
| Porcentaje de recuperación | 100 × pagos del periodo / (pagos del periodo + saldo pendiente actual); cero si el denominador es cero. Es un indicador operativo, no una tasa sobre una cohorte de cartera inicial. El dashboard mantiene su fórmula original. |
| Deudores activos | Clientes distintos con al menos una deuda de saldo positivo actualmente. |
| Clientes de alto riesgo | Deudores activos con `score_riesgo >= 0.66`; no recalcula el modelo. |
| Clientes con estrategia IA | Clientes distintos con estrategia generada durante el periodo. Los snapshots guardan el total histórico disponible. |
| Clientes contactados IA | Clientes distintos con envío válido ligado explícitamente a una estrategia durante el periodo. |
| Clientes con pago post IA | Clientes distintos con al menos un pago del periodo asociado temporalmente a una estrategia. El contacto puede preceder el inicio del periodo hasta la ventana configurada. |
| Recuperación asociada a IA | Suma de esos pagos, cada pago una sola vez. |
| Tasa de pago post IA | 100 × clientes con pago asociado a un contacto del periodo / clientes contactados IA del periodo; cero sin contactos. |
| Recuperación acumulada en evolución | Suma de todos los pagos válidos hasta la fecha de cada snapshot, capturada en ese momento; en operación incluye los pagos históricos válidos existentes. Los snapshots del SQL demo son ficticios y deben interpretarse como tales. |

## 12. Activación y migración

Antes de iniciar el backend actualizado, ejecutar `python -m app.migrate` con la configuración habitual del entorno. Es una migración aditiva e idempotente: añade `comunicaciones.estrategia_id INTEGER NULL REFERENCES historial_mensajes(id)` y su índice; crea `metricas_snapshots`, con importes `NUMERIC(18,2)`, contadores enteros y fecha única. No rellena comunicaciones antiguas ni crea historia previa. No ejecuta seeds ni cambia credenciales.

## 13. Verificación

1. Ejecutar la migración antes del despliegue (no se ha aplicado automáticamente a la base operativa).
2. Entrar con Microsoft Entra y abrir **Analítica IA** en el menú. Cambiar entre 30/90/180 días y 1 año; pulsar **Actualizar datos**.
3. Verificar estado vacío en una base de pruebas sin registros, un snapshot de hoy tras consultar y fechas reales cuando se acumule historia.
4. En un entorno de pruebas con `COMMUNICATIONS_REAL_ENABLED=false`, enviar desde la ficha y comprobar `estrategia_id`. El registro simulado no incrementa recuperación asociada ni contactos reales. No activar proveedores para esta validación.
5. Ejecutar `python -m pytest`, `python -m compileall app`; en `frontend-react`, `npm test`, `npm run lint`, `npm run build`; desde raíz `docker compose config --quiet`.

Estas comprobaciones validan comportamiento operativo y consistencia de registros; no son una evaluación estadística del modelo ni una prueba causal de recuperación.

## 14. Limitaciones

Los tests bloquean la red y utilizan SQLite aislado. La concurrencia PostgreSQL se protege por bloqueo y unicidad pero requiere validación de integración sobre PostgreSQL antes de producción. Los importes fuente siguen siendo Float por compatibilidad: se redondean los pagos a centavos y los snapshots usan Numeric. En carteras grandes la asociación carga pagos y comunicaciones del periodo en memoria; conviene evaluar volumen antes de ampliar el MVP. En SendGrid no existe aquí un callback nuevo: sin estado disponible, entrega permanece sin confirmar. La estrategia histórica puede tener origen no verificable y se conserva la advertencia existente en la ficha.

Se verificaron por separado la restauración/coherencia de la demo y dos lotes de Evaluar cartera concurrentes en PostgreSQL aislado, sin acceso a la operativa. Esa prueba no valida la concurrencia de snapshots, pagos o callbacks, ni reemplaza una evaluación de carga. La demo mantiene scores inferidos, 13/14 inicialmente sin evaluar y 15 sin deuda; sus 24 estrategias y comunicaciones simuladas no prueban llamadas generativas ni envíos. Ver [QA](QA.md#validación-posterior-a-mejora-del-modelo).

El entrenamiento sintético limita la interpretación empresarial del score y las salidas generativas requieren revisión humana. La priorización es un índice interno; los indicadores por canal y de recuperación post IA describen asociaciones observadas. Demostrar causalidad requeriría un diseño de evaluación que este módulo no implementa.
