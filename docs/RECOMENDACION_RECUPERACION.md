# Recomendación de estrategia de recuperación (MVP v1)

La ficha muestra una sugerencia determinista calculada en backend mediante
`app/services/recomendacion.py`. Es una regla de negocio del MVP, no una salida
nueva del RandomForest ni una política financiera validada. Los umbrales son
criterios operativos iniciales revisables por negocio. No reemplaza la decisión
humana, no modifica la deuda y no autoriza descuentos ni condiciones financieras.

Se calcula en cada GET `/api/clientes/{id}`, sin persistir ni recalcular riesgo.
La respuesta añade `recomendacion_recuperacion` con `tipo`, `motivo`,
`nivel_atencion` y `requiere_revision_humana`. La recomendación actual es distinta
del mensaje histórico de IA que puede corresponder a otro saldo.

Variables: score de riesgo existente (0–1), segmento existente, suma de saldos
positivos en MXN, mayor atraso de las deudas activas (días naturales respecto a
la fecha local del servidor, mínimo cero), y número de pagos realizados con fecha
y atraso conocido <= 0. No se cuenta historial sin fecha de pago o atraso conocido;
la ausencia de historial no se interpreta como mal comportamiento. No se usan
los supuestos históricos de ML como pagos observados. Una deuda liquidada no
contribuye al saldo ni al atraso.

Primera coincidencia gana:

| Orden | Condición | Tipo | Atención | Revisión humana |
| --- | --- | --- | --- | --- |
| 1 | Saldo no finito o negativo (función pura) | Revisión manual: verificar datos | alta | Sí |
| 2 | Saldo cero | Sin gestión de recuperación | sin atención | No |
| 3 | Score ausente/inválido, segmento desconocido o alguna deuda activa sin vencimiento | Revisión manual: verificar datos | alta | Sí |
| 4 | Atraso >= 90 o (saldo >= $50,000 y atraso >= 30) | Revisión manual para negociación | alta | Sí |
| 5 | Score >= 0.66 o segmento Alto riesgo | Seguimiento prioritario | alta | No |
| 6 | Sin atraso (incluye vencimiento hoy) | Recordatorio preventivo | normal | No |
| 7 | Atraso >= 30 y saldo > $1,000 | Propuesta de plan de pagos | alta | Sí |
| 8 | Resto | Recordatorio de pago | normal | No |

Los datos inválidos o incompletos devuelven el motivo:
“Faltan datos válidos de riesgo o vencimiento; verificar la información antes
de definir una estrategia.” Requieren revisión humana con atención alta,
sin sugerir negociación.
Un saldo de $50,000 con 1 a 29 días de atraso continúa a las reglas siguientes;
por sí solo no activa negociación.

Si score y segmento difieren, cualquiera de los dos indicadores de alto riesgo
activa seguimiento prioritario. Las reglas anteriores conservan precedencia.
Con al menos tres pagos puntuales, score < 0.33 y segmento Bajo riesgo, el motivo
del recordatorio de pago explica que se favorece un contacto cordial. No cambia
condiciones ni elimina alertas. Los umbrales de saldo organizan la gestión, no
representan ofertas. No se proponen cuotas, porcentajes, meses ni montos de pago.
Cualquier plan o negociación requiere revisión/autorización humana.
`requiere_revision_humana=false` solo permite el seguimiento sugerido, nunca
comprometer condiciones financieras.

Groq no participa en esta recomendación y el flujo existente de generación de
mensajes no se modifica ni recibe este dato en este MVP. No hay nuevas llamadas
a Groq, Twilio o SendGrid. Si posteriormente se integra como contexto, debe
pasarse como decisión ya tomada; Groq solo podrá redactar, sin decidir ni inventar
condiciones financieras. No cambia prioridad, pagos ni autenticación.

Ejemplos de entrada a `recomendar_recuperacion` (pagos_puntuales=0 por defecto):

| Score | Segmento | Atraso | Saldo MXN | Pagos puntuales | Salida tipo / revisión humana |
| --- | --- | --- | --- | --- | --- |
| 0.2 | Bajo riesgo | 5 | 2,000 | 3 | Recordatorio de pago / false |
| 0.2 | Bajo riesgo | 0 | 2,000 | 0 | Recordatorio preventivo / false |
| 0.4 | Riesgo medio | 30 | 2,000 | 0 | Propuesta de plan de pagos / true |
| 0.8 | Alto riesgo | 10 | 2,000 | 0 | Seguimiento prioritario / false |
| 0.2 | Bajo riesgo | 60 | 1,000 | 0 | Recordatorio de pago / false |
| 0.2 | Bajo riesgo | 1 | 50,000 | 0 | Recordatorio de pago / false |
| 0.2 | Bajo riesgo | 29 | 50,000 | 0 | Recordatorio de pago / false |
| 0.2 | Bajo riesgo | 30 | 50,000 | 0 | Revisión manual para negociación / true |
| null | Bajo riesgo | 30 | 50,000 | 0 | Revisión manual / true |
| null | No definido | 0 | 0 | 0 | Sin gestión de recuperación / false |

Ejemplo completo para score=0.2, segmento=Bajo riesgo, atraso=30, saldo=2000:

```json
{
  "tipo": "Propuesta de plan de pagos",
  "motivo": "Atraso de 30 a 89 días y saldo mayor a $1,000 MXN. Evaluar viabilidad; cualquier plan requiere revisión/autorización humana, sin cuotas ni plazos preaprobados.",
  "nivel_atencion": "alta",
  "requiere_revision_humana": true
}
```

Pruebas: `venv/bin/pytest tests/test_recomendacion.py`; en `frontend-react`,
`npm test` incluye la visualización y compatibilidad con respuesta sin recomendación.
Las pruebas backend bloquean la red externa mediante `tests/conftest.py`.
