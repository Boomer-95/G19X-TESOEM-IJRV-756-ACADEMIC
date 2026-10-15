# Decisiones técnicas del MVP

Esta nota relaciona las tecnologías previstas con la implementación verificable. La equivalencia se limita al **objetivo funcional del MVP**, no a todas las capacidades de cada plataforma. Los motivos siguientes describen el encaje técnico del alcance local; no acreditan un estudio comparativo de costos, rendimiento o servicios cloud. Los [requerimientos originales](REQUERIMIENTOS_ORIGINALES.txt) se conservan como antecedente; no todo objetivo de esa visión está implementado.

## Azure Machine Learning → scikit-learn y Random Forest local

- **Requisito original:** analizar comportamiento de pago y estimar riesgo para priorizar cobranza.
- **Tecnología usada:** scikit-learn, `RandomForestClassifier`, seis features y bundle local `risk_model.joblib`, consumidos por FastAPI.
- **Motivo en el MVP:** ejecutar entrenamiento e inferencia locales con el mismo pipeline de features, sin incorporar una plataforma Azure ML para demostrar el scoring.
- **Equivalencia funcional acotada:** producir probabilidad de pago, score y segmento para la priorización, tanto individual como por lote. No se implementa Azure Machine Learning.
- **Limitaciones:** 12,000 historiales sintéticos; métricas exclusivamente sintéticas; sin validación empresarial, calibración ni certificación de producción. No hay en el esquema fecha/versión de evaluación ni caducidad automática. No se acredita gestión cloud del ciclo de vida, monitoreo de deriva ni selección predictiva de canal.
- **Posible evolución:** incorporar datos autorizados, validación temporal, calibración y versionado/monitoreo; evaluar Azure ML si el ciclo de vida y escala lo justifican, sin prometer esa migración.

## Azure OpenAI → Groq mediante API compatible

- **Requisito original:** asistencia generativa para redactar estrategias de recuperación y adaptar mensajes.
- **Tecnología usada:** Groq mediante SDK/API compatible con OpenAI, con modelos configurables para estrategias y SMS.
- **Motivo en el MVP:** atender solicitudes de texto desde el backend mediante la integración existente, sin desplegar Azure OpenAI.
- **Equivalencia funcional acotada:** generar texto de apoyo y adaptaciones solicitadas por el operador. No se afirma equivalencia entre modelos, políticas, garantías o capacidades de las plataformas.
- **Limitaciones:** disponibilidad según cuenta/modelo, dependencia externa y posibles errores o alucinaciones; revisión humana obligatoria. No hay fallback de estrategias ante fallo. No calcula riesgo ni aplica descuentos, convenios o reestructuraciones. Evaluar cartera no usa esta integración.
- **Posible evolución:** evaluar proveedor/modelo bajo requisitos de privacidad, calidad, disponibilidad y gobierno; ampliar evaluaciones de fidelidad antes de usar datos reales. Ningún cambio de proveedor está implementado por esta nota.

## Power BI → Analítica integrada con React/Recharts

- **Requisito original:** visibilidad de cartera, seguimiento y resultados de cobranza.
- **Tecnología usada:** endpoints FastAPI/SQLAlchemy y vistas React/Recharts para KPIs, evolución y canales, con snapshots en PostgreSQL.
- **Motivo en el MVP:** presentar los indicadores dentro de la misma aplicación y sesión, usando el estado persistido y las consultas implementadas.
- **Equivalencia funcional acotada:** tableros del alcance de la demo. No se implementa Power BI ni se declara equivalencia con una plataforma BI completa.
- **Limitaciones:** consultas/refresco manual, snapshots de días consultados sin tarea diaria instalada, sin validación de escala empresarial. Recuperación asociada temporalmente ≠ causalidad; la analítica no es un tercer modelo de IA. El SQL contiene snapshots ficticios expresamente identificados.
- **Posible evolución:** integración BI externa si se necesitan otras fuentes, gobierno, distribución o escala; definir métricas y trazabilidad antes de añadirla.

## Azure AI Search → no implementado

- **Requisito previsto:** búsqueda semántica sobre un corpus documental, si llegara a existir esa necesidad.
- **Situación actual:** el MVP consulta datos estructurados de cartera y estrategias guardadas; no hay un corpus documental preparado que requiera búsqueda semántica. No existe índice Azure AI Search, embeddings, recuperación semántica ni RAG.
- **Motivo en el MVP:** no introducir búsqueda documental sin corpus ni caso de uso definido.
- **Equivalencia funcional acotada:** ninguna sustitución de búsqueda semántica. Buscar clientes por nombre, ID o folio es búsqueda estructurada y no equivale a Azure AI Search.
- **Limitaciones:** no permite preguntas semánticas sobre documentación ni respuestas fundamentadas en un corpus.
- **Posible evolución:** definir corpus autorizado, permisos, actualización y evaluación de recuperación; después valorar Azure AI Search u otra solución. Es una posibilidad futura, no una capacidad disponible.

## Separación de responsabilidades

El modelo predictivo estima riesgo; Groq genera texto; Analítica interpreta registros y resultados. La prioridad `score_riesgo × saldo_pendiente` es un **índice interno de ordenamiento, no dinero**: combina riesgo estimado e impacto económico. Ninguna capa demuestra mejora causal de recuperación ni certifica el sistema para producción. Entra y proveedores de envío conservan sus requisitos de configuración; no se sustituyen por estas decisiones.

Referencias: [Modelo ML](MODELO_ML.md), [Evaluar cartera](EVALUAR_CARTERA.md), [Analítica IA](ANALITICA_IA.md) y [Arquitectura](ARQUITECTURA.md).
