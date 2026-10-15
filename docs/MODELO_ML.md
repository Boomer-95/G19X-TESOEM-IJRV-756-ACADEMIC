# Modelo predictivo

## Implementación y contrato

Se mantiene **scikit-learn / `RandomForestClassifier`**, con 200 árboles, profundidad máxima 6, mínimo 10 muestras por hoja, `class_weight="balanced"` y `random_state=42`. El artefacto aprobado es `app/ml/risk_model.joblib`; su bundle conserva `modelo` y `columnas`. La inferencia no reentrena el bosque.

Las seis features conservan el mismo orden en entrenamiento e inferencia:

1. `pct_pagos_tarde`: proporción de pagos con días de atraso positivos.
2. `promedio_dias_atraso`: promedio de días solo entre pagos tardíos; cero si no hay tardíos.
3. `num_pagos_historicos`: registros con días de atraso conocidos; no necesariamente obligaciones distintas.
4. `monto_promedio_pago`: monto promedio de esos registros.
5. `monto_pendiente_actual`: suma de saldos positivos de deudas activas.
6. `num_deudas_activas`: cantidad de esas deudas.

Sin historial se usan supuestos de 0.3 de pagos tardíos, 5 días de atraso y monto promedio 0. No representan comportamiento observado ni neutralidad demostrada. El vencimiento actual no es una feature directa.

La etiqueta positiva `pago_a_tiempo=1` representa el próximo pago a tiempo. `score_riesgo = 1 - probabilidad_pago_a_tiempo`; se persisten probabilidad y score redondeados por separado a tres decimales. Se conservan los umbrales: **Bajo <0.33**, **Medio [0.33,0.66)** y **Alto >=0.66**.

`prioridad = score_riesgo × saldo_pendiente`, redondeada a dos decimales en API. Es un **índice interno de ordenamiento, no dinero**: combina riesgo estimado e impacto económico. No es una pérdida esperada validada ni un importe recuperable. Cuando falta el score se usa cero para ordenar; esto no acredita bajo riesgo y puede resolverse mediante la acción manual Evaluar cartera.

## Entrenamiento sintético aprobado

El modelo fue reentrenado con **12,000 historiales sintéticos**, divididos de forma estratificada en 9,600 de entrenamiento y 2,400 de prueba, con semilla 42. Se conservaron los hiperparámetros y no se optimizó sobre el test.

El generador construye frecuencia de pagos tardíos coherente con su cantidad de pagos y severidad de atrasos. La etiqueta depende principalmente de ese comportamiento: más historial refuerza evidencia buena o mala, sin premiar automáticamente muchos pagos impuntuales. El saldo tiene efecto acotado y saturado; el monto promedio no recibe una relación causal inventada con la mora. Se mantienen choques futuros no observados y sorteo Bernoulli: la etiqueta no es una regla determinista perfecta. El pago objetivo y su probabilidad latente no entran en las features. Los coeficientes del generador son supuestos de simulación, no relaciones financieras estimadas de una cartera real.

| Métrica del test sintético | Resultado aproximado |
| --- | ---: |
| ROC AUC | 0.8464 |
| Accuracy | 0.7558 |
| Precision | 0.6118 |
| Recall | 0.8208 |
| F1 | 0.7010 |

Precision, recall y F1 usan **pago a tiempo = 1** como clase positiva. **Todas las métricas son exclusivamente sintéticas. No representan rendimiento validado sobre cartera empresarial real ni probabilidades calibradas. El modelo no está certificado para producción.**

| Feature | Importancia relativa aproximada |
| --- | ---: |
| `pct_pagos_tarde` | 72.33% |
| `promedio_dias_atraso` | 22.58% |
| `num_pagos_historicos` | 1.47% |
| `monto_promedio_pago` | 1.58% |
| `monto_pendiente_actual` | 1.41% |
| `num_deudas_activas` | 0.64% |

Son importancias relativas por disminución de impureza del Random Forest; **no son porcentajes causales del riesgo ni aportaciones individuales al score**. El comportamiento domina en este bosque; el saldo ya no domina. Correlaciones e interacciones limitan la lectura aislada de cada variable.

Distribución del test sintético de 2,400 observaciones: **704 Bajo (29.33%), 536 Medio (22.33%) y 1,160 Alto (48.33%)**. No es la distribución de los 15 clientes demo ni una cuota esperada de producción. El AUC anterior cercano a .63 y el predominio del segmento medio se conservan solo como línea base histórica en [Auditoría del modelo](AUDITORIA_MODELO_ML.md); las métricas completas están en [EVALUACION_MODELO_ML.json](EVALUACION_MODELO_ML.json).

## Perfiles verificados

Todos tienen 24 pagos, monto promedio 3,000 y dos deudas activas. Los días representan la media entre pagos tardíos.

| Perfil | % tardíos | Días | Saldo | Probabilidad de pago | Score | Segmento |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Buen pagador | 0% | 0 | 10,000 | .933 | .067 | Bajo |
| Ocasionalmente tardío | 25% | 5 | 10,000 | .747 | .253 | Bajo |
| Muy tardío | 100% | 30 | 10,000 | .125 | .875 | Alto |
| Saldo pequeño y mal comportamiento | 100% | 30 | 500 | .147 | .853 | Alto |
| Saldo grande y buen comportamiento | 0% | 0 | 60,000 | .932 | .068 | Bajo |

Estos perfiles comprueban coherencia de comportamiento; no son resultados empresariales. No se garantiza monotonicidad global: el bosque puede presentar pequeñas fluctuaciones locales.

## Evaluación individual, por lote y pagos

`recalcular_riesgo` es el pipeline compartido. La API individual `/ia/calcular-riesgo/{cliente_id}` calcula sin texto generativo. La ficha calcula al generar/regenerar estrategias; reutilizar una ya guardada no recalcula por ese solo hecho.

**Evaluar cartera**, `POST /api/cartera/evaluar`, usa el mismo pipeline local para activos pendientes o con evaluación incompleta. Guarda `Cliente.probabilidad_pago_a_tiempo`, `score_riesgo` y `segmento`; omite evaluaciones completas. Cada cliente confirma o revierte su propia transacción y el lote continúa ante un fallo. No requiere Groq, no genera estrategias, no comunica ni modifica pagos/deudas. No hay reevaluación forzada ni comprobación temporal por fecha o versión del modelo. Ver [contrato, contadores y evidencia PostgreSQL](EVALUAR_CARTERA.md).

Cada pago registrado se asocia a Cliente y Deuda. Sus días de atraso son fecha_pago − fecha_vencimiento, negativos si se paga antes. Tras registrar el pago y reducir saldo se extraen nuevamente las seis features; si quedan deudas activas se ejecuta el bosque y se persisten probabilidad, score y segmento. Si se liquidó todo, no se ejecuta `predict_proba`: probabilidad y score pasan a NULL y segmento a Sin deuda. No se interpreta saldo cero como probabilidad 100%. Un fallo de inferencia revierte toda la transacción del pago. Un pago no garantiza que el score disminuya.

## Coherencia de la demo

`scripts/seed_entrega.py` evalúa mediante `recalcular_riesgo` después de cargar todo el historial ficticio. Los 12 clientes precargados como evaluados ya no tienen scores manuales; las deudas activas del seed reciben la probabilidad correspondiente. El SQL conserva **13 y 14 sin evaluar** (NULL/No definido) y **15 sin deuda** (NULL/Sin deuda). Evaluar cartera modifica solo los campos del Cliente, no la probabilidad almacenada en Deuda.

Conteos: 15 clientes, 23 deudas, 40 pagos, 24 estrategias, 24 comunicaciones simuladas, 15 snapshots y 0 administradores. Todo es ficticio: estrategias y snapshots no acreditan generación real o recuperación empresarial.

## Capas y limitaciones

1. **IA predictiva:** scikit-learn / Random Forest estima pago a tiempo y deriva riesgo.
2. **IA generativa:** Groq redacta estrategias y adapta mensajes; nunca calcula el score. Recibe contexto mínimo, sin secretos ni datos de contacto; requiere revisión humana.
3. **Analítica:** consultas y React/Recharts interpretan riesgos, estrategias, comunicaciones, pagos y snapshots. No es un tercer modelo de IA; recuperación asociada temporalmente no demuestra causalidad.

Antes de producción se requieren historial real autorizado, evaluación temporal, calibración, revisión de equidad, supervisión humana y controles operativos. Clases balanceadas pueden alterar calibración. Ejecutar `python -m app.ml.train_model` reemplaza el artefacto y requiere una decisión explícita, respaldo y reinicio del backend; no forma parte de Evaluar cartera ni de esta revisión documental. Solo cargar bundles propios: joblib puede ejecutar código al deserializar.
