"""Contratos del generador y comportamiento del bosque real, sin scores exactos."""
from datetime import date, timedelta
from itertools import product

import joblib
import numpy as np
import pandas as pd
import pytest

from app import models
from app.ml.features import FEATURE_COLUMNS, extraer_features_cliente
from app.ml.train_model import MODEL_PATH, generar_dataset_sintetico
from app.services import riesgo


@pytest.fixture(scope='module')
def modelo():
    bundle = joblib.load(MODEL_PATH)
    assert bundle['columnas'] == FEATURE_COLUMNS
    return bundle['modelo']


def perfil(pct=0, dias=0, historial=24, saldo=10000, monto=3000, deudas=2):
    return dict(zip(FEATURE_COLUMNS, [pct, dias, historial, monto, saldo, deudas]))


def scores(modelo, filas):
    return 1 - modelo.predict_proba(pd.DataFrame(filas)[FEATURE_COLUMNS])[:, 1]


@pytest.mark.parametrize('historial,saldo,monto,deudas', list(product([12, 24, 48], [500, 10000, 55000], [1000, 15000], [1, 4])))
def test_buen_pagador_menor_riesgo(modelo, historial, saldo, monto, deudas):
    condiciones = dict(historial=historial, saldo=saldo, monto=monto, deudas=deudas)
    bueno, malo = scores(modelo, [perfil(**condiciones), perfil(1, 30, **condiciones)])
    assert bueno < .33
    assert malo >= .66
    assert malo - bueno > .3


@pytest.mark.parametrize('pct', [.25, .5, .75, 1])
def test_atrasos_significativos_no_reducen_riesgo(modelo, pct):
    for saldo in [500, 10000, 55000]:
        # Bosque sin restricción monótona: tolerar solo fluctuaciones pequeñas,
        # nunca una caída material al pasar de 2 a 45 días de atraso.
        bajo, alto = scores(modelo, [perfil(pct, 2, saldo=saldo), perfil(pct, 45, saldo=saldo)])
        assert alto >= bajo - .03


def test_probabilidades_y_segmentos_independientes(modelo):
    df = generar_dataset_sintetico(5000, seed=2026)
    proba = modelo.predict_proba(df[FEATURE_COLUMNS])
    assert np.isfinite(proba).all()
    assert ((proba >= 0) & (proba <= 1)).all()
    np.testing.assert_allclose(proba.sum(axis=1), 1)
    riesgo = np.round(1 - proba[:, 1], 3)
    proporciones = [(riesgo < .33).mean(), ((riesgo >= .33) & (riesgo < .66)).mean(), (riesgo >= .66).mean()]
    # Rangos amplios: cobertura de los tres segmentos, sin forzar tercios.
    assert all(.1 < p < .7 for p in proporciones)


def test_saldo_no_invierte_historial(modelo):
    bueno_grande, malo_pequeno = scores(modelo, [perfil(saldo=60000), perfil(1, 30, saldo=100)])
    assert bueno_grande < malo_pequeno


def test_generador_coherente_reproducible_y_no_determinista():
    df = generar_dataset_sintetico(12000, seed=71)
    pd.testing.assert_frame_equal(df, generar_dataset_sintetico(12000, seed=71))
    assert list(df.columns) == FEATURE_COLUMNS + ['pago_a_tiempo']
    conocidos = df.num_pagos_historicos > 0
    tardios = df.loc[conocidos, 'pct_pagos_tarde'] * df.loc[conocidos, 'num_pagos_historicos']
    np.testing.assert_allclose(tardios, tardios.round())
    assert (df.loc[conocidos & (df.pct_pagos_tarde == 0), 'promedio_dias_atraso'] == 0).all()
    nuevos = df.loc[~conocidos, FEATURE_COLUMNS[:4]]
    assert (nuevos == [.3, 5, 0, 0]).all().all()
    buenos = df.loc[conocidos & (df.pct_pagos_tarde == 0), 'pago_a_tiempo']
    malos = df.loc[conocidos & (df.pct_pagos_tarde == 1), 'pago_a_tiempo']
    assert .02 < malos.mean() < buenos.mean() < .98


@pytest.mark.parametrize('pct,dias', [(0, 0), (.25, 5), (1, 30)])
def test_score_real_y_features_en_inferencia(db, modelo, monkeypatch, pct, dias):
    cliente = models.Cliente(nombre='Perfil sintético')
    db.add(cliente)
    db.flush()
    db.add(models.Deuda(cliente_id=cliente.id, monto_total=10000, saldo_pendiente=10000,
                        fecha_vencimiento=date.today(), estatus='Pendiente'))
    for i in range(24):
        atraso = dias if i < round(pct * 24) else 0
        vencimiento = date.today() - timedelta(days=90 + i)
        db.add(models.Pago(cliente_id=cliente.id, monto=3000,
                           fecha_vencimiento=vencimiento,
                           fecha_pago=vencimiento + timedelta(days=atraso),
                           dias_atraso=atraso))
    db.flush()
    monkeypatch.setattr(riesgo, '_modelo_riesgo', modelo)
    features = extraer_features_cliente(db, cliente)
    assert features['pct_pagos_tarde'] == pct
    esperado = modelo.predict_proba(pd.DataFrame([features])[FEATURE_COLUMNS])[0, 1]
    resultado = riesgo.recalcular_riesgo(db, cliente)
    assert resultado['score_riesgo'] == round(1 - esperado, 3)
    assert resultado['probabilidad_pago_a_tiempo'] == round(esperado, 3)
    assert resultado['score_riesgo'] + resultado['probabilidad_pago_a_tiempo'] == pytest.approx(1)
    score = resultado['score_riesgo']
    assert resultado['segmento'] == ('Bajo riesgo' if score < .33 else 'Riesgo medio' if score < .66 else 'Alto riesgo')
