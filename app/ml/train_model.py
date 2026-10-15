"""Entrena RandomForestClassifier con historiales y eventos futuros sintéticos.

Los coeficientes son supuestos de simulación, no evidencia financiera real.
La etiqueta representa el próximo pago a tiempo y nunca entra en las features.
Uso: python -m app.ml.train_model (reemplaza el bundle local).
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (roc_auc_score, accuracy_score,
                             precision_score, recall_score, f1_score)
import joblib
import os

from app.ml.features import FEATURE_COLUMNS

MODEL_PATH = os.path.join(os.path.dirname(__file__), "risk_model.joblib")


def generar_dataset_sintetico(n: int = 12000, seed: int = 42) -> pd.DataFrame:
    """
    Genera n clientes sintéticos con features realistas y una etiqueta
    (pago_a_tiempo: 1 = probablemente paga a tiempo, 0 = probablemente no).
    """
    rng = np.random.default_rng(seed)

    # Historial previo al evento objetivo. La beta amplia cubre tanto
    # cumplimiento consistente como mora recurrente, sin segmentos etiquetados.
    tendencia_tardia = rng.beta(0.8, 0.8, n)
    num_pagos_historicos = rng.integers(0, 49, n)
    cantidad_tardios = rng.binomial(num_pagos_historicos, tendencia_tardia)
    pct_pagos_tarde = cantidad_tardios / np.maximum(num_pagos_historicos, 1)
    severidad = rng.gamma(2.0, 8.0, n) + 12 * tendencia_tardia
    promedio_dias_atraso = np.where(cantidad_tardios > 0, severidad, 0.0)
    monto_promedio_pago = rng.uniform(500, 20000, n)
    num_deudas_activas = rng.integers(1, 5, n)
    monto_pendiente_actual = rng.uniform(100, 60000, n)

    # Mismos supuestos que extraer_features_cliente para clientes nuevos.
    sin_historial = num_pagos_historicos == 0
    pct_pagos_tarde[sin_historial] = 0.3
    promedio_dias_atraso[sin_historial] = 5.0
    monto_promedio_pago[sin_historial] = 0.0
    df = pd.DataFrame({
        "pct_pagos_tarde": pct_pagos_tarde,
        "promedio_dias_atraso": promedio_dias_atraso,
        "num_pagos_historicos": num_pagos_historicos,
        "monto_promedio_pago": monto_promedio_pago,
        "monto_pendiente_actual": monto_pendiente_actual,
        "num_deudas_activas": num_deudas_activas,
    })

    # Supuestos de simulación, no coeficientes estimados de una cartera real.
    # Frecuencia y severidad dominan; más historial refuerza su evidencia,
    # sin premiar automáticamente a un cliente con muchos pagos tardíos.
    confianza = num_pagos_historicos / (num_pagos_historicos + 12)
    atraso = np.log1p(promedio_dias_atraso) / np.log(31)
    riesgo_base = (
        -2.3 + 3.8 * pct_pagos_tarde + 0.9 * atraso
        + 0.7 * pct_pagos_tarde * atraso
        + 0.7 * confianza * (pct_pagos_tarde - 0.35)
        + 0.25 * monto_pendiente_actual / (monto_pendiente_actual + 15000)
        + 0.12 * (num_deudas_activas - 1)
    )
    # Choques futuros no observados y sorteo Bernoulli: idéntico historial
    # puede producir resultados distintos. El monto promedio no causa mora
    # por sí solo; se conserva la feature por compatibilidad con inferencia.
    ruido = rng.normal(0, 0.55, n)
    prob_no_pago = 1 / (1 + np.exp(-(riesgo_base + ruido)))
    df["pago_a_tiempo"] = (rng.uniform(0, 1, n) > prob_no_pago).astype(int)

    return df


def crear_modelo():
    """Conserva los hiperparámetros originales para aislar el efecto de los datos."""
    return RandomForestClassifier(
        n_estimators=200, max_depth=6, min_samples_leaf=10,
        random_state=42, class_weight="balanced",
    )


def evaluar_modelo(modelo, X, y):
    """Métricas de pago a tiempo (clase positiva 1), sin ajustar al test."""
    probabilidad = modelo.predict_proba(X)[:, list(modelo.classes_).index(1)]
    prediccion = modelo.predict(X)
    score = np.round(1 - probabilidad, 3)
    return {
        "roc_auc": float(roc_auc_score(y, probabilidad)),
        "accuracy": float(accuracy_score(y, prediccion)),
        "precision": float(precision_score(y, prediccion, zero_division=0)),
        "recall": float(recall_score(y, prediccion, zero_division=0)),
        "f1": float(f1_score(y, prediccion, zero_division=0)),
        "segmentos": {"Bajo": int((score < .33).sum()),
                      "Medio": int(((score >= .33) & (score < .66)).sum()),
                      "Alto": int((score >= .66).sum())},
        "importancias": dict(zip(FEATURE_COLUMNS, modelo.feature_importances_.tolist())),
    }


def entrenar():
    import json
    df = generar_dataset_sintetico()
    X_train, X_test, y_train, y_test = train_test_split(
        df[FEATURE_COLUMNS], df["pago_a_tiempo"],
        test_size=0.2, random_state=42, stratify=df["pago_a_tiempo"],
    )
    modelo = crear_modelo()
    modelo.fit(X_train, y_train)
    print("=== Evaluación reservada, exclusivamente sintética ===")
    print(json.dumps(evaluar_modelo(modelo, X_test, y_test), indent=2))
    joblib.dump({"modelo": modelo, "columnas": FEATURE_COLUMNS}, MODEL_PATH)
    print(f"Modelo guardado en: {MODEL_PATH}")


if __name__ == "__main__":
    entrenar()
