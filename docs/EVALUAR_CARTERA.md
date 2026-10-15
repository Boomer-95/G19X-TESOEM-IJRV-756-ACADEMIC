# Evaluar cartera

Acción explícita en Cartera y endpoint autenticado `POST /api/cartera/evaluar`, sin body. Ejecuta únicamente el pipeline local `recalcular_riesgo`, con el `risk_model.joblib` aprobado. No entrena, genera estrategias, consulta Groq ni contacta proveedores. No requiere GROQ_API_KEY ni depende de COMMUNICATIONS_REAL_ENABLED.

## Diferencia con Procesar cliente

**Procesar cliente**, cuando se solicita una estrategia nueva, combina análisis individual, riesgo predictivo y texto de Groq. Reutilizar una estrategia guardada no llama a Groq ni recalcula por ese solo hecho. **Evaluar cartera** termina al guardar riesgo predictivo: no crea estrategia, historial o comunicación, no usa Email/Twilio/SendGrid y no cambia la prioridad por otra fórmula.

El modelo aprobado sigue siendo scikit-learn / RandomForestClassifier con seis features y score = 1 − probabilidad de pago a tiempo. Fue reentrenado con 12,000 historiales sintéticos: AUC .8464, accuracy .7558, precision .6118, recall .8208 y F1 .7010 en test sintético. No son rendimiento empresarial real, probabilidades calibradas ni certificación de producción. [Modelo y límites](MODELO_ML.md).

## Selección y campos

La operación toma IDs de clientes con al menos una deuda con saldo positivo. Bajo bloqueo `FOR UPDATE` de cada cliente vuelve a comprobar su deuda y evaluación. Comparte el bloqueo de cliente usado por pagos y cálculo individual. Dos lotes simultáneos omiten las evaluaciones que el otro ya confirmó.

Se omiten evaluaciones completas: probabilidad y score presentes, finitos, en [0,1], complementarios dentro de .001 y con segmento reconocido. Se procesan las ausentes o incompletas. No hay timestamp ni versión del modelo en el esquema actual: “vigente” significa completa, no una promesa de actualidad temporal. No hay reevaluación forzada. Versionar evaluaciones o permitir “reevaluar todos” queda como mejora futura.

Los únicos campos persistidos son los existentes en Cliente: `probabilidad_pago_a_tiempo`, `score_riesgo` y `segmento`. Corresponden a la probabilidad de pago y el segmento de riesgo solicitados. **No se modifica `Deuda.probabilidad_pago` ni ningún otro campo de deuda o pago.** Las features y umbrales son los del pipeline existente; la prioridad sigue calculándose como `round(score_riesgo × saldo_pendiente, 2)`. Score es adimensional. La prioridad es un **índice interno de ordenamiento, no dinero**: combina riesgo estimado e impacto económico. El lote permite resolver prioridad cero por falta de evaluación individual, pero solo se ejecuta por acción del usuario y los fallos deben revisarse.

## Transacciones y errores

Cada cliente usa una transacción independiente. Un éxito solo se cuenta tras confirmar la escritura. Si falla la inferencia, devuelve valores inválidos o falla persistencia, se revierte íntegramente ese cliente y se continúa con los restantes. Los éxitos anteriores permanecen guardados. No se muestran excepciones internas; se devuelven IDs fallidos y un motivo genérico. Reintentar procesa únicamente los pendientes.

Modelo local ausente: HTTP 503 antes de procesar. Lote procesado, incluso con fallos parciales: HTTP 200 con los conteos y errores. Si un cliente deja de tener deuda mientras el lote espera el bloqueo, se omite y se informa por separado.

Ejemplo comprobado sobre copia de la demo:

```json
{
  "clientes_activos_encontrados": 14,
  "clientes_evaluados": 2,
  "clientes_ya_evaluados_omitidos": 12,
  "clientes_fallidos": 0,
  "clientes_sin_deuda_omitidos": 0,
  "errores": []
}
```

Los cuatro conteos de resultados suman los activos encontrados en la lectura inicial. Clientes creados o activados después de esa lectura se procesarán en la próxima ejecución.

## Interfaz

El botón “Evaluar cartera” incluye ayuda predictiva, estado de carga y bloqueo inmediato por referencia para impedir doble clic. Muestra el resumen y los IDs que fallaron. Al terminar refresca tabla, métricas y ficha abierta; mantiene los filtros elegidos. También refresca tras error de transporte, porque una respuesta perdida podría ocultar escrituras ya confirmadas. No reintenta automáticamente el POST. La tabla muestra score sin formato monetario, segmento y prioridad actualizados.

### Pasos del usuario

1. Abra Cartera y revise **Análisis → Sin evaluar**, aplicando el filtro.
2. Pulse **Evaluar cartera**; evalúa pendientes activos de toda la cartera, no solo filas filtradas.
3. Espere el resultado y lea activos encontrados, evaluados, ya evaluados omitidos y fallidos. Si aparece, “Sin deuda al procesar” cuenta cambios de saldo entre lectura y procesamiento.
4. Quite el filtro Sin evaluar para ver quienes ya lo dejaron; revise score, segmento y orden por Mayor prioridad. La ficha abierta y métricas se actualizan.
5. Ante fallos, revise los IDs y reintente solo cuando corresponda; los éxitos se omitirán. Si falla únicamente el refresco, use Actualizar. [Manual de usuario](MANUAL_USUARIO.md#8-calcular-riesgo-individual-o-por-cartera).

## Verificación aislada

Tests de backend: autenticación, pendientes, ya evaluados, liquidado, salida no finita/fuera de rango, evaluación incompleta, idempotencia, rollback tras escritura parcial y fallo al guardar. Comparan campos completos de deuda, pagos, historial y comunicaciones antes/después. Los tests bloquean la red y espían Groq, registro de comunicaciones, Twilio y SendGrid; se prueban ambos valores de COMMUNICATIONS_REAL_ENABLED.

Tests frontend ejecutan el componente real y el Dashboard mediante el arnés de hooks del proyecto: doble clic, carga, resumen, error parcial, modelo ausente, error de red, refresco vigente, error de refresco, badges, score y prioridad.

Además se restauró `db/base-de-datos.sql` en un PostgreSQL 16 nuevo en `/tmp/motor-evaluacion-*`, sin escucha TCP y sin leer .env. Se probó el backend real con autenticación sustituida exclusivamente en TestClient, red externa bloqueada y spies de proveedores. El clúster fue detenido al finalizar. También se enviaron dos lotes concurrentes: solo dos evaluaciones en total, sin errores ni duplicación de inferencia para clientes ya guardados.

| Cliente | Probabilidad antes → después | Score antes → después | Segmento antes → después | Prioridad antes → después |
|---|---|---|---|---|
| CL-000013 | NULL → .720 | NULL → .280 | No definido → Bajo riesgo | 0 → 5208.00 |
| CL-000014 | NULL → .953 | NULL → .047 | No definido → Bajo riesgo | 0 → 697.95 |

Orden anterior por ID: 12, 10, 6, 3, 11, 5, 9, 8, 4, 2, 7, 1, 13, 14.

Orden posterior: 12, 10, 6, 3, 13, 11, 5, 9, 8, 4, 2, 14, 7, 1.

Además de las respuestas HTTP, la lectura directa de PostgreSQL confirmó: cliente 13 con `probabilidad_pago_a_tiempo=0.72`, `score_riesgo=0.28`, `segmento=Bajo riesgo`; cliente 14 con `.953`, `.047` y `Bajo riesgo`, respectivamente.

El cliente 15 sigue sin deuda y sin score. Ninguna tabla distinta de clientes cambió en esa prueba PostgreSQL; los clientes previamente evaluados tampoco cambiaron. El SQL demo del repositorio conserva 13 y 14 sin evaluar para demostrar la acción. Se comprobaron hashes intactos del modelo, entrenamiento y SQL durante esta fase. No se accedió a la base operativa.

Validaciones históricas de la implementación de Evaluar cartera, no ejecutadas de nuevo durante esta revisión documental:

- `venv/bin/pytest -q tests/test_evaluar_cartera.py tests/test_seed_entrega.py tests/test_api.py tests/test_operaciones.py tests/test_analitica.py tests/test_schema.py`: 133 passed, una advertencia existente de Starlette/AnyIO.
- `npm test` y la ejecución adicional del test de refresco vigente: 43 tests frontend distintos aprobados.
- `npm run lint`: sin errores.
- `npm run build`: correcto; advertencia de Vite por bundle mayor de 500 kB.
- Restauración y prueba PostgreSQL con concurrencia: correctas. Resultado guardado en `/tmp/evaluacion_cartera_pg_resultado.json`; log en `/tmp/evaluacion_pg.log`. Son rutas temporales de aquella ejecución, no artefactos distribuidos ni garantía de conservación en otra máquina.
- `git diff --check` y hashes de modelo, entrenamiento y SQL: correctos.

No se hizo commit ni push.
