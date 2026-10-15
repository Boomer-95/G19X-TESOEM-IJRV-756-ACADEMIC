# Guía de demostración para el asesor

Esta guía prepara una **instalación nueva**, con Docker y Compose v2, Git y Python 3 disponibles. Los datos de `db/base-de-datos.sql` son completamente ficticios y las comunicaciones reales permanecen deshabilitadas. No reutilice la carpeta, la base ni el volumen de una instalación operativa.

## Preparación

Sustituya `URL_DEL_REPOSITORIO_ENTREGADA` por la dirección recibida privadamente:

```bash
git clone URL_DEL_REPOSITORIO_ENTREGADA motor-cobranza-ia
cd motor-cobranza-ia
cp .env.example .env
```

Complete `.env` localmente, sin publicar sus valores:

- `POSTGRES_USER`, `POSTGRES_PASSWORD` y `POSTGRES_DB`: valores para la base nueva del servicio `db`.
- `ENTRA_CLIENT_ID` y `ENTRA_TENANT_ID`: configuración Microsoft entregada privadamente, sin client secret.
- `VITE_ENTRA_CLIENT_ID` y `VITE_ENTRA_TENANT_ID`: deben coincidir exactamente con los dos valores de backend.
- `VITE_ENTRA_API_SCOPE`: exactamente `api://<CLIENT_ID>/access_as_user`, sustituyendo `<CLIENT_ID>` por `ENTRA_CLIENT_ID`.
- `VITE_ENTRA_REDIRECT_URI`: exactamente `http://localhost:8080/`. Esta URI debe estar registrada como redirect SPA en Microsoft Entra. El script comprueba el valor local; no consulta el tenant.
- `COMMUNICATIONS_REAL_ENABLED=false`: obligatorio. No configure Twilio ni SendGrid para esta demo.
- `GROQ_API_KEY`: no es necesaria para **Evaluar cartera**; solo si se necesita generar nuevas estrategias o adaptar SMS/llamadas; recibirla privadamente. Sin ella se pueden consultar los datos y estrategias históricas; las operaciones que requieren IA muestran servicio no configurado.

Para separar el volumen de otra instalación, añada a este `.env` nuevo un `COMPOSE_PROJECT_NAME` exclusivo, por ejemplo `motor-cobranza-demo-asesor`. No cambie el nombre de proyecto de una instalación operativa existente. Los puertos 8000 y 8080 deben estar libres. Docker construye la conexión usando el servicio `db`; no hace falta configurar `DATABASE_URL` para estos comandos.

El acceso Microsoft del evaluador se entrega privadamente. No copie IDs, claves o tokens a capturas públicas ni al repositorio.

## Restauración y despliegue

```bash
chmod +x scripts/restaurar_demo.sh scripts/deploy_demo.sh
./scripts/restaurar_demo.sh
./scripts/deploy_demo.sh
```

`restaurar_demo.sh` levanta solo `db`, espera su healthcheck y consulta si el esquema `public` está vacío. Si contiene tablas, se detiene sin importar, borrar ni reemplazar datos. En una base vacía importa el SQL dentro de una única transacción y consulta realmente los conteos:

| Entidad | Cantidad |
|---|---:|
| clientes | 15 |
| deudas | 23 |
| pagos | 40 |
| historial_mensajes | 24 |
| comunicaciones | 24 |
| metricas_snapshots | 15 |
| administradores | 0 |

`deploy_demo.sh` valida la configuración antes de compilar, espera PostgreSQL, construye backend/frontend, detiene backend y **siempre ejecuta `python -m app.migrate`** antes de arrancar los servicios. Si la migración falla, no continúa al arranque. La migración es aditiva e idempotente. El backend comprueba tablas y columnas antes de aceptar tráfico; ante un esquema incompleto aborta e indica ejecutar la migración.

Abra **http://localhost:8080/** e inicie sesión con la cuenta Microsoft entregada. Documentación de API: http://127.0.0.1:8000/docs; las rutas de negocio requieren autenticación.

## Evaluación predictiva sin proveedores

Los 12 clientes precargados como evaluados tienen scores obtenidos del pipeline local sobre historiales ficticios, sin valores manuales. 13 y 14 quedan inicialmente sin evaluar; 15 está liquidado y sin score.

1. Abra Cartera y revise Sin evaluar.
2. Pulse **Evaluar cartera** y espere la confirmación: en la copia PostgreSQL verificada hubo **14 activos, 2 evaluados, 12 omitidos y 0 fallidos**.
3. Quite el filtro de pendientes para revisar el orden. El 13 pasó a probabilidad .720, score .280, Bajo riesgo y prioridad 5208.00; el 14 a .953, .047, Bajo riesgo y 697.95. El 15 permanece fuera de cartera activa.
4. Confirme que no aumentaron estrategias ni comunicaciones. No se necesita Groq ni credenciales Twilio/SendGrid. Conservar `COMMUNICATIONS_REAL_ENABLED=false` sigue siendo la política de demo para las otras acciones.

Cada cliente se confirma por separado; un fallo revierte ese cliente y el lote continúa. La prioridad score × saldo es un índice interno de ordenamiento, no dinero; combina riesgo estimado e impacto económico. Estas acciones sí cambian los campos de riesgo de la copia conectada: usar únicamente la demo. Los resultados del modelo son sintéticos, no están calibrados ni certificados para producción. [Pasos y contadores](MANUAL_USUARIO.md#8-calcular-riesgo-individual-o-por-cartera).

## Conservación de la demo

- **No usar `docker compose down -v`**: elimina los volúmenes y sus datos.
- **No ejecutar seeds** después de importar el SQL.
- No repetir la restauración en una base con datos: el script se negará. Para actualizar esta demo use `deploy_demo.sh`, que conserva los datos y migra antes del arranque.
- Los mensajes simulados no implican envíos. Algunas pruebas aisladas ejercitan proveedores mediante mocks; nunca se necesitan contactos reales para esta guía.

## Limitación de dependencias de desarrollo

La revisión npm inicial encontró `source-map-js` 1.2.1 (alta), `vite` 5.4.21 (alta) y `esbuild` 0.21.5 (moderada), todos marcados como dependencias de desarrollo en el lockfile. Se actualizó únicamente `source-map-js` a 1.2.2 mediante un patch compatible, eliminando su aviso.

Persisten dos paquetes afectados: Vite y su dependencia esbuild. El registro no ofrece una corrección completa dentro de Vite 5; `npm audit` propone un cambio major. Ese cambio queda aplazado y no se utilizó `--force`. Los avisos incluyen exposición/lectura a través del servidor de desarrollo, manejo de source maps y condiciones específicas de Windows. No exponga Vite en una red pública. La demo Docker sirve el build estático mediante nginx, sin servidor Vite en ejecución; esto limita la exposición, pero no elimina los avisos del entorno de desarrollo.

Detalles originales: [esbuild](https://github.com/advisories/GHSA-67mh-4wv8-2f99), [Vite/source maps](https://github.com/advisories/GHSA-4w7w-66w2-5vf9), [Vite/Windows UNC](https://github.com/advisories/GHSA-v6wh-96g9-6wx3), [Vite/Windows paths](https://github.com/advisories/GHSA-fx2h-pf6j-xcff). Revisar la actualización major en una tarea separada.
