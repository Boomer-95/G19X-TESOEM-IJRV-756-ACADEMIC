import { useState } from 'react';
import { apiFetch } from './api';
import Comunicacion from './Comunicacion';
import { estadoComunicacion } from './estadoComunicacion';

import { fechaVisible, fechaHoraVisible, diasVisible } from './fechas';
const dinero = monto => `$${monto.toLocaleString('es-MX')} MXN`;

function FormularioPago({ deuda, actualizar }) {
  const [monto, setMonto] = useState('');
  const [ocupado, setOcupado] = useState(false);
  const [estado, setEstado] = useState('');
  async function registrar(event) {
    event.preventDefault(); setOcupado(true); setEstado('');
    try {
      const res = await apiFetch(`/api/deudas/${deuda.id}/pagos`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ monto }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Verifica el monto del pago.');
      setMonto('');
      await actualizar(data.sin_deuda_activa ? `Pago de ${dinero(data.pago.monto)} registrado. Sin deuda activa.` : `Pago de ${dinero(data.pago.monto)} registrado. Saldo y riesgo actualizados.`);
    } catch (error) { setEstado(error.message || 'No se pudo registrar el pago.'); }
    finally { setOcupado(false); }
  }
  return <form onSubmit={registrar} className="pago-form">
    <label>Monto del pago <input type="number" min="0.01" max={deuda.saldo_pendiente} step="0.01" required value={monto} onChange={e => setMonto(e.target.value)} /></label>
    <button disabled={ocupado}>{ocupado ? 'Registrando...' : 'Registrar pago'}</button>
    {estado && <p role="alert">{estado}</p>}
  </form>;
}

export default function FichaCliente({ detalle, alActualizar, alRefrescar }) {
  const clienteId = detalle.cliente_id;
  const [confirmacion, setConfirmacion] = useState('');
  const [procesando, setProcesando] = useState(false);
  const [errorAccion, setErrorAccion] = useState('');
  async function actualizar(mensaje) {
    setConfirmacion(mensaje);
    await alActualizar();
  }
  async function procesar(regenerar = false) {
    setProcesando(true); setErrorAccion(''); setConfirmacion('');
    try {
      const res = await apiFetch(`/ia/analizar-riesgo/${clienteId}?regenerar=${regenerar}`, { method: 'POST' });
      const data = await res.json();
      if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'No se pudo procesar el cliente.');
      await actualizar(data.sin_deuda_activa ? 'El cliente no tiene deuda activa.' : data.reutilizada ? 'Se muestra la última estrategia guardada; no se solicitó una nueva.' : 'Riesgo actualizado y nueva estrategia de Groq guardada.');
    } catch (e) { setErrorAccion(e.message || 'No se pudo procesar el cliente.'); }
    finally { setProcesando(false); }
  }
  return <section className="ficha-cliente" aria-label={`Ficha ${detalle.folio}`}>
    <header className="ficha-encabezado"><span className="folio-cliente">{detalle.folio}</span><h3>{detalle.cliente_nombre}</h3></header>
    <dl className="datos-cliente">
      <div className="saldo-destacado"><dt>Saldo pendiente</dt><dd>{dinero(detalle.monto_pendiente)}</dd></div>
      <div><dt>Monto original</dt><dd>{dinero(detalle.monto_original_total)}</dd></div>
      <div><dt>Vencimiento relevante</dt><dd>{fechaVisible(detalle.fecha_vencimiento)}</dd></div>
      <div><dt>Estado de deuda</dt><dd>{detalle.estado_deuda}</dd></div>
      {!detalle.sin_deuda_activa && <div><dt>Días</dt><dd>{diasVisible(detalle.dias_restantes)}</dd></div>}
      <div><dt>Probabilidad de pago a tiempo</dt><dd>{detalle.sin_deuda_activa ? 'No aplica — sin deuda activa' : detalle.probabilidad_pago_a_tiempo == null ? 'Sin calcular' : `${Math.round(detalle.probabilidad_pago_a_tiempo * 100)}%`}</dd></div>
      <div><dt>Score de riesgo</dt><dd>{detalle.sin_deuda_activa ? 'No aplica — sin deuda activa' : !detalle.segmento || detalle.segmento === 'No definido' ? 'Sin calcular' : detalle.score_riesgo ?? 'Sin calcular'}</dd></div>
      <div><dt>Segmento</dt><dd><span className={`badge-segmento ${detalle.sin_deuda_activa ? 'riesgo-indefinido' : {'Alto riesgo': 'riesgo-alto', 'Riesgo medio': 'riesgo-medio', 'Bajo riesgo': 'riesgo-bajo'}[detalle.segmento] || 'riesgo-indefinido'}`}>{detalle.sin_deuda_activa ? 'Sin deuda' : !detalle.segmento || detalle.segmento === 'No definido' ? 'Sin calcular' : detalle.segmento}</span></dd></div>
    </dl>
    <section className="estrategia-cliente" aria-label="Recomendación de recuperación">
      <h4>Recomendación de recuperación · regla de negocio MVP</h4>
      {detalle.recomendacion_recuperacion ? <>
        <p><strong>{detalle.recomendacion_recuperacion.tipo}</strong></p>
        <p>{detalle.recomendacion_recuperacion.motivo}</p>
        <p>Nivel de atención: {detalle.recomendacion_recuperacion.nivel_atencion}</p>
        <p>{detalle.recomendacion_recuperacion.requiere_revision_humana ? 'Requiere revisión/autorización humana.' : 'No requiere revisión humana previa para el seguimiento sugerido.'}</p>
        <p className="texto-secundario">No modifica la deuda ni autoriza condiciones financieras. No reemplaza la decisión humana.</p>
      </> : <p>Recomendación no disponible.</p>}
    </section>
    <section className="estrategia-cliente" aria-label="Canal sugerido">
      <h4>Canal sugerido: {detalle.canal_sugerido?.canal || 'Sin evidencia suficiente'}</h4>
      <p>Confianza de evidencia: {detalle.canal_sugerido?.confianza || 'insuficiente'}</p>
      <p>{detalle.canal_sugerido?.motivo || 'No hay una sugerencia disponible para este cliente.'}</p>
      {detalle.canal_sugerido?.fuente_evidencia === 'simulada' && <p>Sugerencia basada en datos de demostración/simulados.</p>}
      {detalle.canal_sugerido?.fuente_evidencia === 'mixta' && <p>Sugerencia basada en evidencia mixta: datos reales y de demostración/simulados.</p>}
      <p className="texto-secundario">Esta asociación es observacional y no demuestra que el canal haya causado el pago.</p>
    </section>
    {confirmacion && <p role="status">{confirmacion}</p>}
    <div className="estrategia-cliente">{detalle.sin_deuda_activa ? <p>El cliente no tiene obligaciones pendientes. No se requiere estrategia de cobranza.</p> : <>
      {detalle.ultima_estrategia ? <>
        <h4>{detalle.ultima_estrategia.origen_verificado ? 'Última estrategia generada por IA' : 'Última estrategia guardada · origen histórico no verificado'}</h4>
        <p className="texto-secundario">{detalle.ultima_estrategia.origen_verificado && 'Groq · '}{fechaHoraVisible(detalle.ultima_estrategia.fecha)}. Puede corresponder a un saldo anterior.</p>
        <p className="texto-mensaje mensaje-estrategia">{detalle.ultima_estrategia.mensaje}</p>
        <button className="btn-secundario" onClick={() => procesar(true)} disabled={procesando}>{procesando ? 'Procesando...' : 'Regenerar estrategia con IA'}</button>
      </> : <>
        <p>Estrategia IA: No generada</p>
        <button onClick={() => procesar(false)} disabled={procesando}>{procesando ? 'Procesando...' : 'Procesar cliente'}</button>
      </>}
    </>}</div>
    {errorAccion && <p className="mensaje-error" role="alert">{errorAccion}</p>}
    <details className="detalle-operacion">
      <summary>Deudas y registro de pagos ({detalle.numero_deudas})</summary>
    <h4>Deudas</h4>
    <div className="tabla-wrapper"><table className="tabla-cartera">
      <thead><tr><th>Deuda</th><th className="numero">Original</th><th className="numero">Saldo</th><th>Vencimiento</th><th>Estado</th><th>Pago</th></tr></thead>
      <tbody>{detalle.deudas.map(d => <tr key={d.id}>
        <td>{d.id}</td><td className="numero">{dinero(d.monto_original)}</td><td className="numero">{dinero(d.saldo_pendiente)}</td>
        <td>{fechaVisible(d.fecha_vencimiento)}<br />{d.saldo_pendiente > 0 && diasVisible(d.dias_restantes)}</td><td>{d.estatus}</td>
        <td>{d.saldo_pendiente > 0 && <FormularioPago deuda={d} actualizar={actualizar} />}</td>
      </tr>)}</tbody>
    </table></div>
    </details>
    <details className="detalle-operacion"><summary>Historial de pagos ({detalle.pagos.length})</summary>
    {detalle.pagos.length ? <div className="tabla-wrapper"><table className="tabla-cartera">
      <thead><tr><th>Fecha</th><th className="numero">Monto</th><th className="numero">Días de atraso</th><th>Deuda</th></tr></thead>
      <tbody>{detalle.pagos.map(p => <tr key={p.id}><td>{fechaVisible(p.fecha_pago)}</td><td className="numero">{dinero(p.monto)}</td><td className="numero">{p.dias_atraso ?? '—'}</td><td>{p.deuda_id ?? 'Sin asociación histórica'}</td></tr>)}</tbody>
    </table></div> : <p>Sin pagos registrados.</p>}
    </details>
    <details className="detalle-operacion detalle-comunicaciones"><summary>Contacto y comunicaciones ({detalle.comunicaciones.length})</summary>
    <p className="datos-contacto">Email: {detalle.email || 'No registrado'} · Teléfono: {detalle.telefono || 'No registrado'}</p>
    <h4>Historial de comunicaciones</h4>
    <button className="btn-secundario" type="button" onClick={() => { alRefrescar().catch(e => setErrorAccion(e.message)); }}>Actualizar estados</button>
    {detalle.comunicaciones.length ? <div className="tabla-wrapper"><table className="tabla-cartera">
      <thead><tr><th>Canal</th><th>Fecha</th><th>Mensaje</th><th>Estado</th></tr></thead>
      <tbody>{detalle.comunicaciones.map(c => <tr key={c.id}>
        <td>{c.canal}</td><td>{fechaVisible(c.fecha)}</td><td className="texto-mensaje">{c.mensaje}</td>
        <td><span className="badge-estado" data-estado={estadoComunicacion(c)}>{estadoComunicacion(c).slice(String(c.canal).length + 3)}</span></td>
      </tr>)}</tbody>
    </table></div> : <p>Sin comunicaciones registradas.</p>}
    <Comunicacion key={detalle.sin_deuda_activa ? 'sin-deuda' : detalle.ultima_estrategia?.id ?? 'sin-estrategia'} permitirEdicion
      resultado={{ clienteId, estrategiaId: detalle.sin_deuda_activa ? null : detalle.ultima_estrategia?.id, mensaje: detalle.sin_deuda_activa ? '' : detalle.ultima_estrategia?.mensaje || '' }}
      alRegistrar={() => { alRefrescar().catch(e => setErrorAccion(e.message)); }} />
    </details>
  </section>;
}
