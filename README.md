# Motor Inteligente de Cobranza · PluriOne

MVP para consultar cartera, priorizar clientes, registrar pagos y apoyar la recuperación con recomendaciones explicables, mensajes y analítica observacional.

**Tecnologías:** React/Vite, FastAPI, PostgreSQL 16, Docker Compose, Microsoft Entra, scikit-learn/RandomForest; Groq, Twilio y SendGrid como integraciones opcionales.

## Inicio rápido

Requisitos: Git, Docker Desktop (Windows/macOS) o Docker Engine con Compose v2 (Linux), y Python 3.9+ disponible. Use una carpeta e instalación **nuevas**, separadas de cualquier base operativa. Necesita la URL del repositorio y configuración Entra entregadas privadamente.

### Linux/macOS

```bash
git clone https://github.com/Boomer-95/G19X-TESOEM-IJRV-756-ACADEMIC.git motor-cobranza-demo && cd motor-cobranza-demo
cp -n .env.example .env
${EDITOR:-nano} .env  # Complete PostgreSQL y Entra; COMPOSE_PROJECT_NAME exclusivo; COMMUNICATIONS_REAL_ENABLED=false
bash scripts/restaurar_demo.sh
bash scripts/deploy_demo.sh
```

### Windows PowerShell

```powershell
git clone https://github.com/Boomer-95/G19X-TESOEM-IJRV-756-ACADEMIC.git motor-cobranza-demo; if ($LASTEXITCODE -ne 0) { throw 'No se pudo clonar.' }; Set-Location motor-cobranza-demo
if (!(Test-Path .env)) { Copy-Item .env.example .env }
notepad .env  # Complete PostgreSQL y Entra; COMPOSE_PROJECT_NAME exclusivo; COMMUNICATIONS_REAL_ENABLED=false
.\scripts\restaurar_demo.ps1
.\scripts\deploy_demo.ps1
```

Abra **http://localhost:8080/**. La [guía demo](docs/GUIA_DEMO_ASESOR.md) detalla las variables, requisitos y permisos de scripts. Restauración solo en BD vacía; no borra datos. No ejecutar seeds después ni `docker compose down -v`. Mantenga `COMMUNICATIONS_REAL_ENABLED=false`; Groq no es necesario para consultar los escenarios precargados.

## Acceso de prueba

La cuenta y las credenciales de evaluación Microsoft Entra se entregan **de forma privada en TODO Academy**, junto con la configuración necesaria. No existe usuario local de demo ni contraseña incluida en el repositorio. No necesita client secrets.

## Qué se puede demostrar

Cartera y riesgo local; ficha e historial; recomendación de recuperación con revisión humana, sin descuentos automáticos ni modificar deuda; canal sugerido (cliente 1: SMS, 2: WhatsApp, 3: Email; 13: sin evidencia); analítica de asociación temporal, sin atribuir causalidad. Los datos son ficticios y las comunicaciones permanecen simuladas.

## Documentación

[PRD](docs/PRD.md) · [MVP](docs/MVP.md) · [Arquitectura](docs/ARQUITECTURA.md) · [Manual de usuario](docs/MANUAL_USUARIO.md) · [Modelo ML](docs/MODELO_ML.md) · [Analítica IA](docs/ANALITICA_IA.md) · [Decisiones técnicas](docs/DECISIONES_TECNICAS.md) · [Guía demo](docs/GUIA_DEMO_ASESOR.md) · [Recomendación de recuperación](docs/RECOMENDACION_RECUPERACION.md) · [Canal sugerido](docs/CANAL_SUGERIDO.md) · [QA](docs/QA.md).

Configuración, endpoints, desarrollo local, migraciones, proveedores y regeneración del SQL: [referencia técnica completa](docs/REFERENCIA_TECNICA.md), conservada del README anterior.

## Uso de asistentes de IA durante el desarrollo

Se utilizaron asistentes de IA como apoyo para revisión de código, generación/refactorización asistida, propuestas de pruebas, documentación y análisis de errores. El proyecto fue revisado y probado por el responsable; los resultados se verificaron con tests y ejecución local. El uso del asistente no sustituye la responsabilidad sobre el código entregado.
