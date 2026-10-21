# Canal sugerido por cliente (regla analítica MVP)

El GET existente `/api/clientes/{id}` añade `canal_sugerido`, calculado por
`app/services/canal_sugerido.py`. La ficha muestra canal, confianza de evidencia,
motivo y advertencia observacional. No requiere migración, nuevo endpoint ni
modificar la demo. No ejecuta ML ni proveedores y no persiste resultados.

## Datos y estados existentes

Se usan comunicaciones y pagos del mismo cliente, hasta la fecha local del
servidor. Los únicos canales candidatos son Email, SMS y WhatsApp. Llamada se
excluye porque su simulación no aporta evidencia comparable. No se usan el score
de riesgo, la fórmula de prioridad ni condiciones financieras.

Una comunicación evaluable tiene fecha y modo explícito `real` o `simulado`.
`modo=null` u otro valor es origen no verificado, aunque `exitoso=true`; no prueba
que haya existido un envío real. Registros sin fecha se cuentan en el total,
pero no contribuyen al score. Fechas futuras no se incluyen.

Para registros reales se reconocen los estados ya existentes:

- Entrega/lectura: `provider_status=delivered/read` o `estado=Entregado/Leído`.
- Lectura: `read` o `Leído`, subconjunto de entregadas/leídas.
- Fallo: `failed/undelivered/bounced/dropped` o `Fallido/No entregado`.
  Un fallo tiene precedencia sobre flags contradictorios de entrega.
- `Enviado`, `sent`, `accepted`, colas, pendientes y `exitoso=true` por sí solos
  no confirman entrega. SendGrid actualmente solo confirma aceptación; no se
  inventa evidencia de entrega para Email.

Una simulación nunca se cuenta como entrega, lectura o fallo real, aunque tenga
flags heredados. Sí puede tener un pago asociado temporalmente para explorar la
demo. Dos simulaciones sin pagos no bastan para sugerir un canal.

## Asociación temporal de pagos

Ventana configurable mediante `CANAL_SUGERIDO_VENTANA_PAGO_DIAS`, inicialmente 7.
Admite enteros entre 1 y 365; una configuración inválida produce error explícito.
La función también acepta la ventana y fecha de referencia para pruebas.

Solo se consideran pagos realizados (`fecha_pago` conocida, no futura,
`se_recuperó=true`, monto positivo y finito). Por cada pago:

1. Se buscan contactos candidatos del mismo cliente cuya diferencia de fechas
   sea **0 <= fecha_pago - fecha_envio <= ventana**.
2. Se elige una única comunicación: fecha más reciente; a igual día, ID mayor.
3. Se suma una asociación y el monto completo al canal de ese contacto. Si el
   origen del último contacto no está verificado, no se acredita ni se reasigna
   a uno anterior. Se excluye Llamada antes de buscar candidatos.

No se exige estrategia IA ni se utiliza `Pago.canal_contacto`. Se incluyen
contactos fallidos o pendientes en esta coincidencia temporal: un pago posterior
no confirma recepción ni eficacia. Los fallos conservan su penalización. No se
reparte un pago entre canales; varios pagos distintos sí pueden coincidir con
un mismo contacto. Los importes se acumulan con Decimal y se redondean a centavos;
el monto no aumenta el score.

Las fechas de comunicaciones y pagos son `Date`, sin hora: el día cero se incluye
por requisito, pero no es posible probar que el contacto ocurrió primero ese
día. El ID es un desempate reproducible, no una prueba del orden de envío.

## Score y elección

Para cada canal:

```
P = número de pagos asociados temporalmente
L = comunicaciones leídas reales
E = comunicaciones entregadas reales SIN lectura
F = comunicaciones fallidas/no entregadas reales
score_interno = 5*P + 3*L + 2*E - 2*F
```

Una lectura no recibe también los dos puntos de entrega. El score es un criterio
operativo arbitrario del MVP, documentado y probado; **no es una probabilidad ni
una precisión estadística**. Solo compiten canales con al menos **dos** contactos
evaluables y score **estrictamente positivo**. Si no hay ninguno:
`canal=null`, `estado=Sin evidencia suficiente`, `confianza=insuficiente`.

Orden de selección, de mayor a menor:

1. Score interno.
2. Número de pagos asociados temporalmente.
3. Tasa de entregadas/leídas sobre comunicaciones evaluables (fracción exacta).
4. Cantidad de comunicaciones evaluables.
5. Orden fijo: Email, SMS, WhatsApp; únicamente desempate, sin preferencia comercial.

## Evidencia y confianza

`estadisticas` tiene una entrada por canal con comunicaciones totales/evaluables,
entregadas/leídas, leídas, fallidas/no entregadas, pagos y monto asociados
 temporalmente, última fecha de comunicación y score interno. También desglosa
reales, simuladas y no evaluables. El total incluye registros sin fecha o de
origen desconocido; el score solo usa los evaluables. La última fecha no incluye
registros sin fecha.

`fuente_evidencia` global describe el historial candidato y por canal describe su
historial: `real`, `simulada`, `mixta`, `no_verificada` (solo origen desconocido)
o `sin_datos` (sin registros). Si hay origen desconocido junto con conocido,
la fuente describe los modos conocidos; el contador no evaluable advierte la
limitación. No se reclasifica legado como real.

Confianza describe **solo cantidad/calidad de evidencia del canal elegido**:

- Baja: mínimo elegible; también cualquier canal con evidencia simulada o mixta.
- Media: canal de fuente real, >=5 contactos evaluables y >=2 entregadas/leídas.
- Alta: canal de fuente real, >=10 contactos evaluables, >=3 pagos asociados y
  entregadas/leídas >=4/5 de sus contactos evaluables.
- Insuficiente: ningún canal cumple el mínimo y score positivo.

Se evalúa alta antes de media. El historial global puede ser mixto aunque el
canal elegido sea real; la confianza se calcula sobre ese canal. La interfaz
identifica expresamente datos de demostración/simulados o evidencia mixta.

## Ejemplos reproducibles

1. Cliente A: dos SMS entregados, dos Email fallidos y sin pagos.
   SMS=4, Email=-4; sugiere **SMS**, confianza baja, fuente real.
2. Cliente B: dos WhatsApp leídos y dos SMS entregados, sin pagos.
   WhatsApp=6, SMS=4; sugiere **WhatsApp**, confianza baja, fuente real.
3. Cliente C: dos Email simulados y un pago tres días después del último.
   Email=5; sugiere **Email**, confianza baja, fuente simulada. La interfaz muestra
   “Sugerencia basada en datos de demostración/simulados”. Sin ese pago no sugiere.

## Límites

La asociación es observacional y no demuestra que el canal haya causado el pago.
Puede haber otros contactos, acuerdos u otros factores no registrados. Los
pesos y mínimos no se han validado estadísticamente. Múltiples abonos y volúmenes
altos pueden dominar el score. El historial no tiene caducidad adicional a la
ventana por pago y puede reflejar comportamientos antiguos. Las fechas diarias,
la falta de callbacks de entrega de Email y el origen legado desconocido limitan
la comparación entre canales. No se consideran disponibilidad de datos de
contacto, preferencias o consentimientos; esta sugerencia no autoriza envíos ni
reemplaza la revisión del asesor. No decide condiciones financieras.

El servicio y su GET solo leen objetos existentes; no escriben en PostgreSQL ni
modifican pagos/comunicaciones. Los tests usan SQLite aislado, bloquean red y
verifican que el GET solo ejecuta SELECT, sin ejecutar ML o proveedores.
