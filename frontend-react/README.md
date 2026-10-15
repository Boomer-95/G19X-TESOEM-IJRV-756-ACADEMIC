# Frontend de cobranza

Usar un solo frontend durante cada ejecución y prueba de sesión:

- Docker/Nginx: http://localhost:8080
- Desarrollo Vite: http://localhost:5173

Son orígenes diferentes. La caché de MSAL está configurada en `sessionStorage`,
con ámbito de origen y pestaña; no asumir una sesión compartida entre puertos
ni sincronización automática entre pestañas. Cada entorno necesita su URI de
redirección registrada. No utilizarlos simultáneamente para probar la misma sesión.

## Autenticación Microsoft Entra ID / MSAL

La única autenticación es Microsoft Entra ID. React utiliza
`@azure/msal-browser` y `@azure/msal-react` con **Authorization Code con PKCE**
y redirecciones. `MsalProvider` gestiona la inicialización y el retorno de MSAL;
**Iniciar sesión con Microsoft** ejecuta `loginRedirect` con selección de cuenta.
No existe login local legacy, formulario de usuario/contraseña local ni JWT
emitido por la aplicación. `/auth/login` no existe como ruta de acceso.

La configuración de `src/auth/msalConfig.js` requiere:

| Variable | Uso |
| --- | --- |
| `VITE_ENTRA_CLIENT_ID` | Client ID del registro Microsoft existente. |
| `VITE_ENTRA_TENANT_ID` | Tenant de la autoridad Microsoft. |
| `VITE_ENTRA_API_SCOPE` | Scope delegado exacto `api://<CLIENT_ID>/access_as_user`. |
| `VITE_ENTRA_REDIRECT_URI` | URI de retorno del entorno, también usada tras logout. |

Los marcadores no son valores para copiar literalmente. Sin configuración válida
se muestra un aviso y no se permite iniciar sesión. No se usa client secret en
la SPA. Estas variables se resuelven al compilar; para Vite local se configuran
en el entorno o en `frontend-react/.env.local`, no se carga automáticamente el
`.env` de la raíz. Detalles en [README — Microsoft Entra](../README.md#microsoft-entra).

## Access token para la API

El inicio de sesión solicita `openid` y `profile`. Para acceder al backend,
`src/auth/getAccessToken.js` obtiene un **access token** para el scope delegado
`access_as_user` de esta API mediante `acquireTokenSilent`. Si Microsoft exige
interacción, utiliza `acquireTokenRedirect`; no se presupone que un token
expirado obligue siempre a iniciar sesión de nuevo.

`apiFetch` obtiene el token antes de cada solicitud y añade
`Authorization: Bearer <access_token>`. No envía el ID token ni un token de
Microsoft Graph para autorizar esta API. Evita enviar una solicitud cancelada
o cuya cuenta cambió durante la obtención del token. El backend valida firma
RS256, emisor, audiencia, tenant, vigencia, versión v2 y scope delegado.

**MSAL administra la caché en `sessionStorage`. No guardar tokens manualmente
en `localStorage` ni mantener una clave propia `token`.** No copiar tokens a
capturas, logs ni herramientas públicas.

## Sesión e historial

La aplicación comienza en **Validando sesión...**, sin mostrar el dashboard.
Cuando MSAL termina sus interacciones y existe una cuenta activa, consulta
`/auth/me` con `cache: 'no-store'` y solo monta el dashboard tras una respuesta
válida con identidad. Sin cuenta muestra Login. Un fallo de validación bloquea
el acceso y desmonta los datos visibles; el código no gestiona borrado manual
de tokens. Si hay varias cuentas y ninguna selección activa válida, no elige
una arbitrariamente.

`pageshow` (incluido el retorno desde BFCache), `popstate` y volver a una
pestaña visible comprueban nuevamente la sesión. `pagehide` oculta el dashboard
antes de guardar la página en BFCache. El historial guarda secciones, nunca
autorización; volver atrás no sustituye la revalidación.

Cerrar sesión bloquea el acceso local, desmonta cartera, selección, métricas,
resultados e historial, e invoca `logoutRedirect` de MSAL. Si falla el cierre en
Microsoft, aparece un error; no se promete revocación instantánea de access
tokens ya emitidos. Las respuestas de validaciones canceladas no restauran
una sesión anterior.

`apiFetch` invalida la sesión visible ante 401 o 403 de una solicitud vigente
de la cuenta actual. Una respuesta tardía de otra cuenta o de una solicitud
cancelada no invalida la nueva sesión. Las validaciones y cambios de estado
están implementados en `src/useSesion.js`.

## Verificación manual

Preparar entradas de historial navegando entre secciones del dashboard.
En DevTools, usar Network para comprobar `/auth/me` y ralentizar la red para
ver **Validando sesión...** sin mostrar datos. No editar ni extraer tokens.

| Caso | Pasos | Resultado esperado |
| --- | --- | --- |
| A | Login Microsoft → Dashboard → Cerrar sesión → Atrás | No reaparece cartera sin revalidación; sin cuenta autorizada, Login. |
| B | Navegar atrás/adelante tras cerrar sesión | No se recuperan datos sensibles del dashboard anterior. |
| C | Volver al dashboard cuando el access token necesita renovación | MSAL intenta adquisición silenciosa; si requiere interacción, redirige a Microsoft. Un fallo no deja visible el dashboard. |
| D | Con cuenta válida, recargar | Validando sesión → obtención de access token → `/auth/me` válido → Dashboard. |
| E | En una prueba controlada, simular 401/403 o error de conexión en `/auth/me` | Se bloquea el acceso y se oculta el dashboard; no hay login local de respaldo. |

Para BFCache, salir a otra página en la misma pestaña y volver con Atrás;
comprobar con la herramienta Back/forward cache del navegador que la
restauración es real. Verificar también rechazo 401/403 de la cuenta actual
en un endpoint protegido. No asumir que cerrar otra pestaña borra esta caché
ni usar eliminación de claves de `localStorage` como prueba de logout.

Estas comprobaciones interactivas requieren una cuenta y configuración Entra
válidas. Los tests locales usan transporte e identidad simulados; no certifican
login real ni comportamiento visual del navegador. Validaciones de código:
`npm test`, `npm run lint` y `npm run build`.

## Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react/README.md) uses [Babel](https://babeljs.io/) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh
