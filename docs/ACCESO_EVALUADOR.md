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

## Errores comunes

| Situación | Comprobación y acción |
| --- | --- |
| Cuenta no perteneciente o no autorizada en el tenant | Elegir la cuenta dedicada. El responsable debe confirmar que está autorizada en el tenant configurado y asignada a la aplicación si esta lo exige. No usar la cuenta personal del desarrollador como solución. |
| Redirect URI incorrecto | Confirmar **`http://localhost:8080/`**, incluida la barra final, en la plataforma SPA del registro existente y en `VITE_ENTRA_REDIRECT_URI`. No sustituir localhost por otra dirección durante esta demo. |
| Scope incorrecto o API devuelve 403 | Confirmar el permiso delegado **`api://<CLIENT_ID>/access_as_user`**, la configuración/consentimiento necesario en Entra y `VITE_ENTRA_API_SCOPE`. Backend espera `access_as_user` en `scp`; no acepta un ID token ni un token de Microsoft Graph como acceso a esta API. |
| Variables Entra incompletas o mensaje de configuración ausente | Completar `ENTRA_CLIENT_ID`, `ENTRA_TENANT_ID`, sus equivalentes `VITE_ENTRA_*`, scope y redirect. Los IDs de frontend y backend deben coincidir. `ENTRA_REQUIRED_SCOPE` tiene valor predeterminado `access_as_user`; conservarlo. Reconstruir/aplicar la configuración siguiendo la guía demo. |
| API devuelve 401 o se está usando otra sesión | Cerrar sesión y repetir en incógnito con la cuenta dedicada. El backend rechaza tokens inválidos, expirados o de otra audiencia/tenant. |
| API devuelve 503 al validar Microsoft | El responsable debe comprobar la configuración y conectividad de discovery/JWKS de Entra; no desactivar la validación ni compartir tokens como solución. |

## Checklist antes de entregar

- [ ] Crear o confirmar cuenta Microsoft dedicada de evaluación.
- [ ] Confirmar que puede iniciar sesión en el tenant.
- [ ] Confirmar que Assignment required = No, o que la cuenta tenga asignación si aplica.
- [ ] Confirmar redirect URI http://localhost:8080/
- [ ] Confirmar scope `api://<CLIENT_ID>/access_as_user`.
- [ ] Probar desde una ventana de incógnito.
- [ ] Confirmar acceso al dashboard y HTTP 200 en la petición autenticada a `/auth/me`.
- [ ] Cerrar sesión y repetir una segunda vez.
- [ ] Subir usuario/contraseña SOLO en TODO Academy → Técnicos → Accesos de prueba (dentro de Mis documentos).
- [ ] Confirmar que ninguna credencial aparece en GitHub.

Si el registro exige asignación, asignar la cuenta dedicada sin relajar esa
política. Mantener las políticas de seguridad del tenant; si algún requisito
impide la evaluación, el responsable debe resolver el acceso antes de entregar.
Las pruebas automatizadas del repositorio usan tokens y claves ficticios y no
sustituyen esta prueba interactiva real con la cuenta dedicada.
