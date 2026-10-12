import { useEffect, useState } from 'react';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { apiFetch } from './api';
import { mxn } from './formatoAnalitica';

const fecha = value => new Date(`${value}T12:00:00`).toLocaleDateString('es-MX');

const mxnEje = value => new Intl.NumberFormat('es-MX', {
  style: 'currency', currency: 'MXN', notation: 'compact', maximumFractionDigits: 1,
}).format(value);
const fechaEje = value => new Date(value).toLocaleDateString('es-MX', { day: '2-digit', month: 'short' });

export function Serie({ titulo, datos = [], campo, color = '#0f5b99' }) {
  const serie = datos.map(d => ({ ...d, instante: new Date(`${d.fecha}T12:00:00`).getTime(), monto: Number(d[campo]) }))
    .filter(d => Number.isFinite(d.instante) && d[campo] != null && Number.isFinite(d.monto))
    .sort((a, b) => a.instante - b.instante);
  if (!serie.length) return <article className="grafica-analitica"><h3>{titulo}</h3><div className="analitica-vacia"><p>Sin datos suficientes para graficar.</p><p>La recopilación comienza al activar este módulo.</p></div></article>;
  // Un único snapshot se muestra como marcador, sin inventar fechas o importes.
  const dominio = serie.length === 1
    ? [serie[0].instante - 86400000, serie[0].instante + 86400000]
    : ['dataMin', 'dataMax'];
  return <article className="grafica-analitica"><h3>{titulo}</h3>
    <p className="analitica-unidad">Importes en MXN · {serie.length} {serie.length === 1 ? 'registro disponible' : 'registros disponibles'}</p>
    <div className="analitica-linea" role="group" aria-label={`${titulo}, valores en MXN`}>
      <ResponsiveContainer width="100%" height="100%" minWidth={0}>
        <LineChart data={serie} margin={{ top: 12, right: 20, bottom: 8, left: 0 }} accessibilityLayer>
          <CartesianGrid stroke="#edf0f4" vertical={false} />
          <XAxis dataKey="instante" type="number" scale="time" domain={dominio}
            ticks={serie.length <= 2 ? serie.map(d => d.instante) : undefined}
            tickFormatter={fechaEje} minTickGap={36} tick={{ fontSize: 11, fill: '#5f6b76' }} tickLine={false} axisLine={{ stroke: '#d8dee4' }} />
          <YAxis tickFormatter={mxnEje} width={88} domain={[0, max => Math.max(1, max * 1.1)]}
            tick={{ fontSize: 11, fill: '#5f6b76' }} tickLine={false} axisLine={false} />
          <Tooltip labelFormatter={value => new Date(Number(value)).toLocaleDateString('es-MX')}
            formatter={value => [mxn(value), 'Monto MXN']} cursor={{ stroke: '#94a3b8', strokeDasharray: '3 3' }}
            contentStyle={{ border: '1px solid #dde3eb', borderRadius: 0, boxShadow: 'none', fontSize: 12, padding: '12px 16px' }} />
          <Line type="linear" dataKey="monto" name="Monto MXN" stroke={color} strokeWidth={2}
            dot={{ r: 3, fill: color, stroke: '#fff', strokeWidth: 2 }} activeDot={{ r: 5 }} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
    <details><summary>Ver fechas y montos</summary><div className="tabla-analitica"><table><thead><tr><th>Fecha</th><th>Monto MXN</th></tr></thead><tbody>{serie.map(d => <tr key={d.fecha}><td>{fecha(d.fecha)}</td><td>{mxn(d.monto)}</td></tr>)}</tbody></table></div></details>
  </article>;
}

export function PanelAnalitica({ datos, cargando, error }) {
  if (cargando) return <p role="status">Cargando analítica…</p>;
  if (error) return <p role="alert">No se pudo cargar la analítica. Usa Actualizar datos para reintentar.</p>;
  if (!datos) return <p>Sin datos disponibles.</p>;
  const { resumen: r, evolucion, canales } = datos;
  const kpis = [['Saldo vencido', mxn(r.cartera_vencida)], ['Monto recuperado en el período', mxn(r.monto_recuperado_total)],
    ['Recuperación del período', `${r.porcentaje_recuperacion}%`], ['Clientes de alto riesgo', r.clientes_alto_riesgo],
    ['Clientes con estrategia IA', r.clientes_con_estrategia_ia], ['Recuperación asociada a IA', mxn(r.monto_recuperado_post_ia)]];
  const comparacion = [['Clientes con estrategia IA', r.clientes_con_estrategia_ia], ['Clientes contactados con estrategia IA', r.clientes_contactados_ia], ['Clientes con pago posterior a estrategia IA', r.clientes_con_pago_post_ia]];
  const maximo = Math.max(1, ...comparacion.map(([, valor]) => valor));
  return <>
    <p className="analitica-actualizacion">Última actualización: {new Date(r.ultima_actualizacion).toLocaleString('es-MX')}</p>
    <p className="texto-secundario analitica-aviso">Recuperación asociada temporalmente a una estrategia IA: pagos de los {r.ventana_ia_dias} días posteriores a un envío real aceptado. No representa causalidad demostrada. Se excluyen envíos simulados y pagos del mismo día.</p>
    <div className="grid-metricas">{kpis.map(([titulo, valor]) => <div key={titulo} className="tarjeta-metrica"><h3>{titulo}</h3><div className="valor">{valor}</div></div>)}</div>
    {!r.deudores_activos && !r.monto_recuperado_total && <p>Sin cartera activa ni pagos en este periodo.</p>}
    <div className="analitica-contexto"><p>Los importes se muestran en MXN. Los saldos y el riesgo muestran el estado actual. Pagos y estrategias corresponden al periodo seleccionado.</p>
    <p>Histórico disponible desde: {r.inicio_historico ? fecha(r.inicio_historico) : 'la activación del módulo'}. Se guardan únicamente los días consultados; no se reconstruyen fechas anteriores.</p></div>
    <div className="analitica-graficas">
      <Serie titulo="Evolución de cartera vencida" datos={evolucion} campo="cartera_vencida" />
      <Serie titulo="Recuperación histórica acumulada · MXN" datos={evolucion} campo="monto_recuperado" color="#287659" />
      <article className="grafica-analitica analitica-estrategias"><h3>Estrategias IA / pagos posteriores</h3>{comparacion.map(([titulo, valor]) => <div key={titulo} className="barra-analitica"><span>{titulo}: {valor}</span><meter min="0" max={maximo} value={valor} aria-label={titulo} /></div>)}<p className="analitica-tasa">Tasa de pago posterior en la cohorte contactada: <strong>{r.tasa_pago_post_ia}%</strong></p></article>
      <article className="grafica-analitica analitica-canales"><h3>Efectividad por canal</h3><p>Envíos aceptados y pagos asociados; la entrega solo se confirma con estado del proveedor.</p>
        {canales.map(c => <div className="barra-analitica" key={c.canal}><span>{c.canal}: {c.comunicaciones_enviadas} enviadas · {c.pagos_posteriores_asociados} pagos posteriores</span><meter min="0" max={Math.max(1, ...canales.map(v => v.comunicaciones_enviadas))} value={c.comunicaciones_enviadas} aria-label={`Enviadas ${c.canal}`} /></div>)}
        <div className="tabla-analitica"><table><thead><tr><th>Canal</th><th>Enviadas</th><th>Entregadas</th><th>Fallidas</th><th>Simuladas</th><th>Clientes únicos</th><th>Pagos asociados</th><th>Monto MXN</th></tr></thead><tbody>{canales.map(c => <tr key={c.canal}><td>{c.canal}</td><td>{c.comunicaciones_enviadas}</td><td>{c.entregadas}</td><td>{c.fallidas}</td><td>{c.simuladas}</td><td>{c.clientes_unicos_contactados}</td><td>{c.pagos_posteriores_asociados}</td><td>{mxn(c.monto_recuperado_post_ia)}</td></tr>)}</tbody></table></div>
        {!canales.some(c => c.comunicaciones_enviadas) && <p>Sin envíos reales aceptados en este periodo.</p>}
      </article>
    </div>
  </>;
}

export default function Analitica({ referenciaSeccion }) {
  const [dias, setDias] = useState(30);
  const [revision, setRevision] = useState(0);
  const [datos, setDatos] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    setCargando(true); setError(false);
    async function cargar() {
      try {
        // Evolución crea/actualiza el snapshot de hoy antes de consultar el resumen.
        async function obtener(ruta) {
          const res = await apiFetch(`/api/analitica/${ruta}?dias=${dias}`, { signal: controller.signal });
          if (!res.ok) throw new Error('Consulta fallida');
          return res.json();
        }
        const evolucion = await obtener('evolucion');
        const [resumen, canales] = await Promise.all([obtener('resumen'), obtener('canales')]);
        if (!controller.signal.aborted) setDatos({ resumen, evolucion, canales });
      } catch { if (!controller.signal.aborted) setError(true); }
      finally { if (!controller.signal.aborted) setCargando(false); }
    }
    cargar();
    return () => controller.abort();
  }, [dias, revision]);
  return <section id="analitica" ref={referenciaSeccion} tabIndex={-1} aria-labelledby="titulo-analitica" className="panel-analitica">
    <div className="analitica-encabezado"><div><p className="etiqueta-seccion">Seguimiento de resultados</p><h2 id="titulo-analitica">Analítica IA · Impacto de Cobranza</h2></div>
    <div className="input-group"><label>Periodo <select aria-label="Periodo de analítica" value={dias} onChange={e => setDias(Number(e.target.value))}>{[[30, '30 días'], [90, '90 días'], [180, '180 días'], [365, '1 año']].map(([valor, etiqueta]) => <option key={valor} value={valor}>{etiqueta}</option>)}</select></label><button disabled={cargando} onClick={() => setRevision(r => r + 1)}>Actualizar datos</button></div>
    </div>
    <PanelAnalitica datos={datos} cargando={cargando} error={error} />
  </section>;
}
