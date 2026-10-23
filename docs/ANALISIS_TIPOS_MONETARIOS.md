# Análisis de Tipos Monetarios y Viabilidad de Migración

## 1. Diagnóstico Actual

En la arquitectura actual del sistema, las columnas monetarias operativas definidas en `app/models.py` y en el esquema inicial `db/base-de-datos.sql` (`Deuda.monto_total`, `Deuda.saldo_pendiente`, `Pago.monto` y `HistorialMensaje.monto_al_momento`) están declaradas con el tipo `Float` de SQLAlchemy (`DOUBLE PRECISION` en PostgreSQL). El uso de coma flotante binaria (IEEE 754) en persistencia conlleva el riesgo inherente de imprecisión decimal en operaciones aritméticas acumuladas.

No obstante, **la capa de negocio y validación ya mitiga este riesgo en las operaciones críticas**:
- **Registro de pagos (`app/routers/pagos.py`)**: El esquema de entrada `PagoNuevo` exige `Decimal` (`max_digits=14, decimal_places=2, allow_inf_nan=False`) y convierte el saldo pendiente mediante `Decimal(str(deuda.saldo_pendiente)).quantize(Decimal("0.01"))` antes de validar y descontar pagos.
- **Propuestas de recuperación (`app/services/recomendacion.py`)**: Los cálculos de quitas, descuentos y cuotas mensuales se ejecutan íntegramente con `Decimal` y redondeo financiero `ROUND_HALF_UP` a `Decimal("0.01")`.
- **Analítica e indicadores (`app/services/analitica.py`, `app/services/canal_sugerido.py`, `MetricaSnapshot`)**: Las sumatorias de pagos y asociación temporal cuantifican en `Decimal(".01")`, y la tabla `metricas_snapshots` ya almacena saldos en `Numeric(18, 2)`.

## 2. Limitaciones de la Infraestructura

El proyecto no cuenta actualmente con **Alembic** para el versionado y ejecución de migraciones de esquema:
- La creación de tablas depende de `Base.metadata.create_all(engine)` (en `app/migrate.py`, `scripts/seed_entrega.py` y `tests/conftest.py`) y de un script aditivo ligero (`app/migrate.py`) diseñado únicamente para agregar columnas faltantes (`ALTER TABLE ... ADD COLUMN`).
- `Base.metadata.create_all` **no ejecuta `ALTER COLUMN TYPE`** sobre tablas existentes. Cambiar `Column(Float)` a `Column(Numeric(14, 2))` en `app/models.py` dejaría las bases de datos PostgreSQL existentes desincronizadas respecto al ORM (`DOUBLE PRECISION` en motor físico frente a `Numeric` en SQLAlchemy) o requeriría reescritura completa de tablas bajo bloqueo exclusivo (`ACCESS EXCLUSIVE LOCK`).

## 3. Riesgo de Regresión Crítica

Forzar el cambio de las columnas ORM de `Float` a `Numeric(14, 2)` en esta etapa introduce dos vectores de regresión severa:

1. **Choque de tipos en memoria (`TypeError: float * Decimal`)**:
   - El motor de riesgo (`scikit-learn`) y el cálculo de prioridad en `app/main.py` (`resumen_cliente`) operan con probabilidades y scores en `float` (`prioridad = round((c.score_riesgo or 0) * saldo, 2)`).
   - Al retornar `Decimal` desde SQLAlchemy para `saldo_pendiente` y `monto`, Python lanza `TypeError: unsupported operand type(s) for *: 'float' and 'decimal.Decimal'` en la priorización de cartera y altera los tipos esperados por el pipeline de features (`app/ml/features.py`).
2. **Corrupción de `contexto_hash` (SHA-256) y ruptura de la suite de pruebas**:
   - En `app/routers/ia.py`, la huella criptográfica del contexto enviado a Groq se calcula con `json.dumps(contexto, sort_keys=True, ensure_ascii=False, default=str)`.
   - Mientras que un `float` se serializa en JSON como número (`1500.0`), un `Decimal` procesado por `default=str` se serializa como cadena con dos decimales (`"1500.00"`). Esto alteraría todos los hashes SHA-256 (`contexto_hash`), invalidando la trazabilidad histórica de estrategias generadas por IA y rompiendo las aserciones de la suite actual de **579 pruebas automatizadas**.

## 4. Veredicto Técnico

La migración profunda de las columnas ORM `Float` a `Numeric(14, 2)` queda **formalmente postergada a la Fase 2 (Post-MVP)**. Su ejecución deberá realizarse de forma conjunta con:
1. La incorporación de **Alembic** para gestionar migraciones transaccionales de tipos en PostgreSQL (`ALTER COLUMN ... TYPE NUMERIC(14,2) USING ...`).
2. Una refactorización integral y controlada de las fronteras de tipos entre SQLAlchemy, el pipeline de Machine Learning (`float`) y el serializador canónico de `contexto_hash` para preservar la compatibilidad del scoring y del historial de IA.
