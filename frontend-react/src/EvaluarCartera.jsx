import { useRef, useState } from 'react';
import { apiFetch } from './api';

export default function EvaluarCartera({ alEvaluar }) {
  const pendiente = useRef(false);
  const alEvaluarActual = useRef(alEvaluar);
  alEvaluarActual.current = alEvaluar;
  const [cargando, setCargando] = useState(false);
  const [resultado, setResultado] = useState(null);
  const [error, setError] = useState('');

  async function evaluar() {
    if (pendiente.current) return;
    pendiente.current = true;
    setCargando(true); setResultado(null); setError('');
    try {
      const respuesta = await apiFetch('/api/cartera/evaluar', { method: 'POST' });
      if (!respuesta.ok) {
        throw new Error(respuesta.status === 503
          ? 'El modelo predictivo local no está disponible.'
          : 'No se pudo completar la evaluación predictiva.');
      }
      setResultado(await respuesta.json());
    } catch (fallo) {
      setError(fallo.message);
    } finally {
      // Una respuesta perdida puede ocultar clientes ya guardados: refrescar
      // también tras error, sin repetir automáticamente el POST.
      try {
        await alEvaluarActual.current();
      } catch {
        setError('No se pudo actualizar la vista. Pulsa Actualizar para consultar los resultados guardados.');
      }
      pendiente.current = false;
      setCargando(false);
    }
  }

  return (
    <div className="evaluacion-cartera" aria-busy={cargando}>
      <button type="button" onClick={evaluar} disabled={cargando} aria-describedby="ayuda-evaluar-cartera">
        {cargando ? 'Evaluando cartera...' : 'Evaluar cartera'}
      </button>
      <p id="ayuda-evaluar-cartera" className="texto-secundario">Calcula el riesgo predictivo de clientes activos pendientes de evaluación.</p>
      {cargando && <p role="status">Calculando riesgo predictivo...</p>}
      {resultado && <div role="status">
        <p>Activos encontrados: {resultado.clientes_activos_encontrados}. Evaluados: {resultado.clientes_evaluados}. Ya evaluados omitidos: {resultado.clientes_ya_evaluados_omitidos}. No pudieron evaluarse: {resultado.clientes_fallidos}.</p>
        {resultado.clientes_sin_deuda_omitidos > 0 && <p>Sin deuda al procesar: {resultado.clientes_sin_deuda_omitidos}.</p>}
        {resultado.errores?.length > 0 && <p>Clientes pendientes por error: {resultado.errores.map(e => e.cliente_id).join(', ')}. Puedes reintentar la evaluación.</p>}
      </div>}
      {error && <p role="alert" className="mensaje-error">{error}</p>}
    </div>
  );
}
