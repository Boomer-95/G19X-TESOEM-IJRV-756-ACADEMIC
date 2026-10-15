# Auditoría y mejora del modelo de riesgo — 2026-10-15

**Lectura histórica:** esta auditoría corresponde a la mejora del modelo antes de aprobar y regenerar la demo. El AUC .6283, la distribución anterior y los scores manuales mencionados como hallazgos no describen el estado actual. El estado aprobado está en [Modelo ML](MODELO_ML.md) y [Evaluar cartera](EVALUAR_CARTERA.md).

Se inspeccionaron entrenamiento, extracción de features, inferencia en `app/main.py`, modelos ORM, seeds (`app/seed.py`, `app/ml/seed_historial.py`, `scripts/seed_entrega.py`), generación/validación de SQL demo y tests de API, operaciones, analítica y demo antes de modificar código. No se modificaron endpoints, frontend, esquema, seeds ni SQL. Se conservaron los cambios previos del usuario en otros documentos.

## Modelo y contrato existentes

Entrenamiento: `app/ml/train_model.py`. Inferencia: `recalcular_riesgo` en `app/main.py`. Bundle: `app/ml/risk_model.joblib`, claves `modelo` y `columnas`.

Orden exacto de features, conservado:

| Feature | Significado |
|---|---|
| pct_pagos_tarde | Pagos con atraso positivo / pagos con atraso conocido |
| promedio_dias_atraso | Media de días exclusivamente de pagos tardíos; cero si ninguno |
| num_pagos_historicos | Número de registros con atraso conocido; no necesariamente obligaciones distintas |
| monto_promedio_pago | Media del importe de los pagos con atraso conocido |
| monto_pendiente_actual | Suma de saldos positivos de deudas activas |
| num_deudas_activas | Número de esas deudas |

Sin historial: porcentaje .3, días 5, cantidad 0, monto promedio 0. Son supuestos, no neutralidad demostrada.

RandomForestClassifier de scikit-learn: `n_estimators=200`, `max_depth=6`, `min_samples_leaf=10`, `class_weight="balanced"`, `random_state=42`; restantes parámetros por defecto. No se cambiaron hiperparámetros ni se realizó búsqueda sobre el test.

La etiqueta original era un Bernoulli: pago a tiempo si uniforme > sigmoid(1.8×porcentaje + .03×días + .00003×saldo + .15×deudas − .02×historial + Normal(0,.4) − 1.5). Generaba 2,000 registros, con features independientes: porcentaje Beta(2,5), días Gamma(2,5), historial entero [0,24), monto promedio uniforme [500,20000), saldo uniforme [0,40000) y deudas enteras [0,5). No respetaba las fracciones posibles según historial ni los defaults sin historial. Favorecía más historial incluso malo; ofrecía poca cobertura de porcentajes tardíos extremos. El monto promedio era independiente de la etiqueta, pero adquiría importancia espuria.

## Nuevo dataset y prevención de leakage

12,000 clientes independientes; la mayor muestra reduce variabilidad por ruido y da cobertura de historiales cortos/largos y extremos. Tendencia tardía Beta(.8,.8); 0–48 pagos previos; cantidad tardía binomial; porcentaje obtenido de esa cantidad. Si hay tardíos, días Gamma(2,8) + 12×tendencia; si no, cero. Clientes nuevos usan exactamente los defaults de producción. Se modelan clientes con deuda activa: 1–4 deudas y saldo entre 100 y 60,000. El monto promedio es independiente (500–20,000, o cero sin historial); se conserva por compatibilidad, sin inventar relación causal por tamaño de pago.

Logit de impuntualidad futura:

```
confianza = historial / (historial + 12)
atraso = log(1 + días) / log(31)
logit = -2.3 + 3.8×porcentaje + .9×atraso
        + .7×porcentaje×atraso
        + .7×confianza×(porcentaje - .35)
        + .25×saldo/(saldo + 15000) + .12×(deudas - 1)
        + Normal(0, .55)
```

El saldo tiene efecto saturado y acotado a .25 en el logit. Más historial refuerza evidencia buena o mala; su importancia individual puede ser pequeña por interacción y correlación. El cumplimiento queda representado por frecuencia y severidad; no se agrega una feature redundante ni se cambia el contrato.

La etiqueta es un sorteo Bernoulli posterior a construir las features. No se incorpora el pago objetivo, su fecha, su resultado ni probabilidad latente al vector de entrada. Choques futuros no observados y Bernoulli permiten incumplimientos entre buenos pagadores y cumplimiento entre malos. No se asignan etiquetas por umbrales. División estratificada 80/20 con semilla 42: 9,600 entrenamiento, 2,400 test. Se conserva el bosque entrenado únicamente con train; no se ajustó después de medir test. No se hicieron iteraciones de selección de coeficientes por AUC del test.

## Antes y después

Clase positiva para precision/recall/F1: **pago a tiempo = 1**. Importancia = disminución de impureza del bosque; no equivale a causalidad ni a efecto porcentual sobre el score.

| Métrica | Antes, test original (400) | Después, test nuevo (2,400) |
|---|---:|---:|
| ROC AUC | .6283 | .8464 |
| Accuracy | .6050 | .7558 |
| Precision | .6121 | .6118 |
| Recall | .6359 | .8208 |
| F1 | .6238 | .7010 |
| Bajo | 32 (8.0%) | 704 (29.33%) |
| Medio | 322 (80.5%) | 536 (22.33%) |
| Alto | 46 (11.5%) | 1,160 (48.33%) |

Precision permanece prácticamente igual; no mejoran todas las métricas. La prevalencia cambia con los supuestos del generador, por lo que esta tabla no aísla una mejora sobre una población fija.

| Importancia | Antes | Después |
|---|---:|---:|
| pct_pagos_tarde | 17.68% | 72.33% |
| promedio_dias_atraso | 15.68% | 22.58% |
| num_pagos_historicos | 12.67% | 1.47% |
| monto_promedio_pago | 15.85% | 1.58% |
| monto_pendiente_actual | 27.83% | 1.41% |
| num_deudas_activas | 10.30% | .64% |

También se evaluaron ambos bosques, ya congelados, sobre **la misma muestra independiente** del generador nuevo: 10,000 clientes, semilla 20261015. Ninguno entrenó sobre esta muestra. Sus etiquetas favorecen por construcción las nuevas hipótesis; tampoco demuestra mejora real.

| Métrica | Bosque anterior | Bosque nuevo |
|---|---:|---:|
| ROC AUC | .6874 | .8468 |
| Accuracy | .6785 | .7590 |
| Precision | .5479 | .6177 |
| Recall | .4733 | .8200 |
| F1 | .5079 | .7046 |
| Bajo/Medio/Alto | 2.08% / 67.96% / 29.96% | 28.44% / 23.47% / 48.09% |

## Perfiles comparables

Todos: 24 pagos, monto promedio 3,000 y 2 deudas activas. Días: media entre pagos tardíos. Score redondeado a 3 decimales, igual que inferencia. Umbrales conservados: <.33 Bajo; [.33,.66) Medio; >=.66 Alto.

| Perfil | % tarde | Días | Saldo | Prob. pago a tiempo | Score nuevo | Segmento | Score anterior |
|---|---:|---:|---:|---:|---:|---|---:|
| Buen pagador | 0% | 0 | 10,000 | .933 | .067 | Bajo | .311 |
| Ocasionalmente tardío | 25% | 5 | 10,000 | .747 | .253 | Bajo | .370 |
| Muy tardío | 100% | 30 | 10,000 | .125 | .875 | Alto | .524 |
| Saldo pequeño, mal comportamiento | 100% | 30 | 500 | .147 | .853 | Alto | .532 |
| Saldo grande, buen comportamiento | 0% | 0 | 60,000 | .932 | .068 | Bajo | .478 |

## Validación y límites

Tests nuevos: 36 combinaciones comparables de historial, saldo, monto y deudas; atrasos de 2 a 45 días con tolerancia máxima .03 para fluctuación del bosque; probabilidades finitas en [0,1]; suma de clases uno; cobertura de tres segmentos en 5,000 observaciones independientes (semilla 2026); consistencia y reproducibilidad del generador; etiquetas no deterministas; extracción real vía SQLite y contrato score = 1 − probabilidad con redondeo. No memorizan predicciones exactas. No se garantiza monotonicidad global: el Random Forest conserva sus hiperparámetros y puede presentar fluctuaciones locales.

Los resultados son exclusivamente sintéticos. Los coeficientes son supuestos explícitos, no relaciones financieras estimadas. Clases balanceadas pueden alterar calibración: no interpretar estas probabilidades como calibradas en cartera real. La distribución razonable aplica a esta simulación, no fija cuotas para producción. Se requiere validación temporal y calibración con historial real para afirmar calidad predictiva real.

**Hallazgo en aquella fase:** `scripts/seed_entrega.py` fijaba scores .15/.48/.82 sin inferencia. Durante la auditoría del modelo se conservaron seed/SQL pendientes de aprobación. **Resuelto posteriormente:** el generador y SQL demo aprobados usan el pipeline real para los 12 evaluados, conservando 13/14 sin evaluar y 15 sin deuda. La posterior acción Evaluar cartera procesa los pendientes sin Groq; no se recalcularon datos operativos. Las cifras de esta auditoría permanecen como evidencia histórica, no como una nueva medición documental.

Reproducir entrenamiento y test reservado: `venv/bin/python -m app.ml.train_model`. Métricas completas y features de perfiles: `docs/EVALUACION_MODELO_ML.json`. La línea base fue medida antes de modificar y coincidió exactamente entre el artefacto original y reentrenarlo con el generador original. Para repetirla debe recuperarse esa versión original del generador y bundle, sin usar el nuevo para medir la línea base.

Validación ejecutada: `venv/bin/pytest -q tests/test_risk_model.py tests/test_api.py tests/test_operaciones.py tests/test_analitica.py`: **147 passed**, una advertencia de deprecación existente en Starlette/AnyIO. La ejecución con TestClient se bloqueó en sandbox; se detuvo y se ejecutó fuera del sandbox. `git diff --check` sin errores. Sin commit ni push.
