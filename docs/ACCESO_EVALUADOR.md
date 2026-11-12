# Acceso de evaluación

La aplicación utiliza **Microsoft Entra ID como único mecanismo de autenticación**.
El frontend usa MSAL; el backend valida el access token de Entra y el permiso
`access_as_user`. No existe usuario local, login alternativo, JWT emitido por la
aplicación, modo de autenticación demo ni bypass. La tabla legacy de
administradores no proporciona acceso.

Para la evaluación se proporciona una **cuenta Microsoft de prueba dedicada**,
identificada en esta guía como `CUENTA_EVALUACION_ENTREGADA_PRIVADAMENTE`. El
revisor no necesita la cuenta personal del desarrollador. La cuenta dedicada debe
estar creada o autorizada en el tenant Entra configurado y tener acceso a la
aplicación; una cuenta Microsoft cualquiera no basta. El sistema sigue dependiendo
de ese tenant y su disponibilidad, no de compartir la sesión personal del autor.

La creación, autorización y prueba de la cuenta se realizan **manualmente en
Azure/Entra** por el responsable. Esta documentación no acredita que esas tareas
ya estén completadas: deben verificarse con el checklist antes de entregar.

## Entrega privada

El usuario y la contraseña de la cuenta dedicada **no se almacenan en GitHub**,
ni en Markdown, código, SQL, `.env.example`, issues, workflows o capturas públicas.
Se entregan exclusivamente mediante:

**TODO Academy → Mis documentos → Técnicos → Accesos de prueba → PERFIL.md**.

La configuración necesaria para la instalación se comparte por ese mismo canal
privado y se completa localmente según la [guía demo](GUIA_DEMO_ASESOR.md). No
subir `.env` a GitHub. No adjuntar tokens, claves API ni secretos del tenant. El
frontend SPA es un cliente público y **no requiere client secret**; no debe
configurarse ninguno como variable `VITE_*`.

## Cómo entrar

1. Levante la instalación de demo siguiendo la [guía del asesor](GUIA_DEMO_ASESOR.md).
   Mantenga `COMMUNICATIONS_REAL_ENABLED=false`; el acceso no requiere habilitar
   proveedores de comunicaciones.
2. Abra **http://localhost:8080/**.
3. Seleccione **“Iniciar sesión con Microsoft”**.
4. Use `CUENTA_EVALUACION_ENTREGADA_PRIVADAMENTE` y la contraseña recibida por el
   canal privado. Complete los pasos adicionales que Microsoft solicite según
   las políticas del tenant.
5. Al regresar a la aplicación debe aparecer el dashboard.

Si ya existe otra sesión Microsoft abierta, utilice una ventana privada/incógnito
o cierre sesión de la cuenta anterior y vuelva a iniciar con la cuenta dedicada.
La selección de cuenta se realiza en Microsoft; no se introducen credenciales en
un formulario local de PluriOne.

## Verificar el acceso

Además de ver el dashboard, puede comprobar en la pestaña **Red/Network** de las
herramientas del navegador que la solicitud autenticada a **`/auth/me`** responde
**HTTP 200** y devuelve la identidad con `id` (y nombre/email cuando estén
disponibles). En Docker la ruta visible es **`/backend/auth/me`**, mediante el
proxy de http://localhost:8080/; la API directa expone `/auth/me` en el puerto 8000.

La aplicación obtiene y adjunta automáticamente el access token a esta petición.
Abrir la URL directamente en la barra del navegador no adjunta ese token y puede
responder 401: eso no demuestra un fallo de la sesión de la aplicación. No copie
tokens ni cabeceras Authorization a documentación o capturas. Verifique también
que la identidad corresponde a la cuenta dedicada, sin publicar sus datos.

## Escenarios de ejecución y Redirect URI en Microsoft Entra ID

La configuración MSAL del frontend (`frontend-react/src/auth/msalConfig.js`) utiliza la variable `VITE_ENTRA_REDIRECT_URI` tanto para `redirectUri` como para `postLogoutRedirectUri`. Microsoft Entra ID exige que la URI enviada por el navegador coincida exactamente (esquema, host, puerto y barra final `/`) con una URI registrada en la plataforma **Single-page application (SPA)** del App Registration.

| Escenario | Puerto y origen del frontend | Valor requerido en `VITE_ENTRA_REDIRECT_URI` | Estado del registro en Microsoft Entra ID |
| --- | --- | --- | --- |
| **Con Docker Compose** (escenario de demostración principal) | Puerto **8080** (`http://localhost:8080/`, servido por Nginx) | `http://localhost:8080/` | **Confirmado y verificado** en las pruebas de entrega (Linux y Windows 10). |
| **Sin Docker** (ejecución manual con Vite: `npm run dev`) | Puerto **5173** (`http://localhost:5173/`, servidor de desarrollo Vite) | `http://localhost:5173/` | **Confirmado y verificado** en prueba real sin Docker en Linux Mint (12 de noviembre de 2026). |

### Qué debe comprobar el administrador en el portal de Microsoft Entra

Antes de utilizar el escenario manual sin Docker en el puerto `5173` (o al revisar la configuración del registro existente), el administrador del tenant debe verificar en **Microsoft Entra admin center** (o Azure Portal):

1. Ir a **App registrations** → abrir la aplicación correspondiente a `ENTRA_CLIENT_ID` / `VITE_ENTRA_CLIENT_ID` → sección **Authentication**.
2. Bajo la plataforma **Single-page application (SPA)** (cliente público, sin client secret), comprobar las **Redirect URIs** registradas:
   - Para el escenario **Docker**: debe estar registrada `http://localhost:8080/`.
   - Para el escenario **sin Docker (Vite)**: debe agregarse y guardarse `http://localhost:5173/` en esa misma plataforma SPA.
3. Confirmar que el entorno local del frontend use la URI correspondiente al puerto activo:
   - En Docker: `VITE_ENTRA_REDIRECT_URI=http://localhost:8080/` en `.env` (aplicada al compilar la imagen `frontend`).
   - Sin Docker: `VITE_ENTRA_REDIRECT_URI=http://localhost:5173/` y `VITE_API_URL=http://127.0.0.1:8000` en `frontend-react/.env.local` o exportadas en la terminal antes de ejecutar `npm run dev` (Vite no lee automáticamente el `.env` de la raíz).

### Consecuencias de usar un puerto cuyo Redirect URI no está registrado

- **Si `VITE_ENTRA_REDIRECT_URI` apunta a `http://localhost:5173/` pero esa URI no está registrada en Entra ID:** al pulsar **“Iniciar sesión con Microsoft”** (`loginRedirect` o `acquireTokenRedirect`), Microsoft Entra ID bloqueará el flujo OAuth 2.0 / OIDC con un error de validación de redirección (por ejemplo, `AADSTS50011: The redirect URI 'http://localhost:5173/' specified in the request does not match the redirect URIs configured for the application...`), impidiendo autenticar al usuario, obtener el access token para `/auth/me` y cargar el dashboard.
- **Si se abre el frontend en `http://localhost:5173/` manteniendo `VITE_ENTRA_REDIRECT_URI=http://localhost:8080/`:** tras autenticarse en Microsoft, el navegador será redirigido a `http://localhost:8080/` en lugar de regresar al servidor Vite en `5173`, por lo que la aplicación en el puerto `5173` no recibirá la respuesta de autenticación ni establecerá la sesión en `sessionStorage`.

## Errores comunes

| Situación | Comprobación y acción |
| --- | --- |
| Cuenta no perteneciente o no autorizada en el tenant | Elegir la cuenta dedicada. El responsable debe confirmar que está autorizada en el tenant configurado y asignada a la aplicación si esta lo exige. No usar la cuenta personal del desarrollador como solución. |
| Redirect URI incorrecto | Confirmar **`http://localhost:8080/`** (escenario Docker) o **`http://localhost:5173/`** (escenario manual con Vite, previo registro en el portal), incluida la barra final, tanto en la plataforma SPA del registro en Entra como en `VITE_ENTRA_REDIRECT_URI`. No sustituir localhost por otra dirección durante esta demo. |
| Scope incorrecto o API devuelve 403 | Confirmar el permiso delegado **`api://<CLIENT_ID>/access_as_user`**, la configuración/consentimiento necesario en Entra y `VITE_ENTRA_API_SCOPE`. Backend espera `access_as_user` en `scp`; no acepta un ID token ni un token de Microsoft Graph como acceso a esta API. |
| Variables Entra incompletas o mensaje de configuración ausente | Completar `ENTRA_CLIENT_ID`, `ENTRA_TENANT_ID`, sus equivalentes `VITE_ENTRA_*`, scope y redirect. Los IDs de frontend y backend deben coincidir. `ENTRA_REQUIRED_SCOPE` tiene valor predeterminado `access_as_user`; conservarlo. Reconstruir/aplicar la configuración siguiendo la guía demo. |
| API devuelve 401 o se está usando otra sesión | Cerrar sesión y repetir en incógnito con la cuenta dedicada. El backend rechaza tokens inválidos, expirados o de otra audiencia/tenant. |
| API devuelve 503 al validar Microsoft | El responsable debe comprobar la configuración y conectividad de discovery/JWKS de Entra; no desactivar la validación ni compartir tokens como solución. |

## Checklist antes de entregar

- [X] Crear o confirmar cuenta Microsoft dedicada de evaluación.
- [X] Confirmar que puede iniciar sesión en el tenant.
- [X] Confirmar que Assignment required = No, o que la cuenta tenga asignación si aplica.
- [X] Confirmar redirect URI http://localhost:8080/
- [X] Confirmar scope `api://<CLIENT_ID>/access_as_user`.
- [X] Probar desde una ventana de incógnito.
- [X] Confirmar acceso al dashboard y HTTP 200 en la petición autenticada a `/auth/me`.
- [X] Cerrar sesión y repetir una segunda vez.
- [X] Subir usuario/contraseña SOLO en TODO Academy → Técnicos → Accesos de prueba (dentro de Mis documentos).
- [X] Confirmar que ninguna credencial aparece en GitHub.

**Fecha de la última prueba exitosa de acceso:** 29 de octubre de 2026 (realizada con la cuenta Microsoft dedicada de evaluación y su propia contraseña, sin utilizar el correo personal del desarrollador).
**Última prueba completa de la cuenta dedicada:** 3 de noviembre de 2026 (incógnito, dashboard y `/auth/me` con 200 en `http://localhost:8080/`), complementada el 10 de noviembre de 2026 en Windows 10 (inicio de sesión Microsoft Entra ID y acceso al dashboard en `http://localhost:8080/`).
**Prueba local con PostgreSQL local, FastAPI y Vite fuera de Docker (Linux Mint):** 12 de noviembre de 2026 en `http://localhost:5173/` con FastAPI en `http://127.0.0.1:8000` y PostgreSQL local `16.15` (`motor_cobranza_local`).

### Registro de prueba local con PostgreSQL, FastAPI y Vite fuera de Docker (12 de noviembre de 2026)

El **12 de noviembre de 2026** se ejecutó en **Linux Mint** una prueba real ejecutando PostgreSQL local, FastAPI y React/Vite fuera de Docker (durante la sesión el contenedor `motor_cobranza-db-1` permaneció activo en segundo plano, pero no fue utilizado por ninguno de los servicios de esta prueba):

#### Lo comprobado expresamente en esta prueba

- **Base de datos local:** PostgreSQL `16.15` con la base independiente `motor_cobranza_local`. La base se creó inicialmente con propietario `admin` e importó `db/base-de-datos.sql` con `SET ROLE admin`; posteriormente se creó el rol dedicado `motor_cobranza_local_app` (sin modificar la contraseña del rol compartido `admin` ni otras bases), se reasignaron los objetos y la propiedad de la base a `motor_cobranza_local_app` y se verificó la conexión TCP con dicho rol.
- **Datos importados:** `15` clientes, `23` deudas, `40` pagos, `24` registros en `historial_mensajes`, `24` en `comunicaciones`, `15` en `metricas_snapshots` y `0` en `administradores`.
- **Migración:** ejecución correcta de `python -m app.migrate` con el rol propietario `motor_cobranza_local_app`, conservando los datos importados.
- **Servicios fuera de Docker:** FastAPI iniciado en `http://127.0.0.1:8000` y React/Vite iniciado en `http://localhost:5173/`.
- **Autenticación Microsoft Entra ID y dashboard:** inicio de sesión exitoso en `http://localhost:5173/` y acceso al dashboard, que mostró:
  - Deudores activos: `14`
  - Saldo vencido: `$92,400`
  - Clientes con estrategia IA: `12`
  - Clientes sin evaluar: `2`
  - Recuperación: `41.6%`
- **Consulta de cartera y fichas:** la sección de clientes mostró los `15` registros y permitió abrir sus fichas individuales y consultar sus deudas.

#### Lo que no se volvió a verificar expresamente en esta prueba local

- La inspección directa de la respuesta **HTTP 200 de `/auth/me`** en la pestaña Red/Network del navegador y la repetición del flujo de cierre de sesión y segundo inicio en incógnito ya se habían comprobado en las pruebas previas sobre Docker (`http://localhost:8080/`), pero **no se volvieron a verificar expresamente de forma individual durante esta sesión en Vite (`http://localhost:5173/`)** más allá del inicio de sesión Microsoft exitoso y la carga autenticada del dashboard y de la cartera.
- Tampoco se ejecutaron en esta sesión operaciones de escritura sobre `motor_cobranza_local` (pagos, *Evaluar cartera* o generación de estrategias con Groq) ni envíos reales por proveedores externos (`COMMUNICATIONS_REAL_ENABLED=false`).

Si el registro exige asignación, asignar la cuenta dedicada sin relajar esa
política. Mantener las políticas de seguridad del tenant; si algún requisito
impide la evaluación, el responsable debe resolver el acceso antes de entregar.
Las pruebas automatizadas del repositorio usan tokens y claves ficticios y no
sustituyen esta prueba interactiva real con la cuenta dedicada.
