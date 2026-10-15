import Analitica from './Analitica';
import EvaluarCartera from './EvaluarCartera';
import { useState, useEffect, useCallback, useRef } from 'react';
import './App.css';
import useNavegacionSecciones, { SECCIONES } from './useNavegacionSecciones';
import Login from './Login';
import useSesion from './useSesion';
import Historial from './Historial';
import FichaCliente from './FichaCliente';
import Icono from './Icono';
import { fechaVisible, diasVisible } from './fechas';
import { apiFetch } from './api';

const SEGMENTO_INFO = {
  'Alto riesgo': { clase: 'riesgo-alto', label: 'Alto riesgo' },
  'Riesgo medio': { clase: 'riesgo-medio', label: 'Riesgo medio' },
  'Bajo riesgo': { clase: 'riesgo-bajo', label: 'Bajo riesgo' },
  'No definido': { clase: 'riesgo-indefinido', label: 'Sin calcular' },
};

function BadgeSegmento({ segmento }) {
  const info = SEGMENTO_INFO[segmento] || SEGMENTO_INFO['No definido'];
  return (
    <span className={`badge-segmento ${info.clase}`}>
      {info.label}
    </span>
  );
}

function App() {
  const { estado, admin, errorSesion, cerrar } = useSesion();
  if (estado === 'validando') {
    return <div className="login-wrapper"><p role="status">Validando sesión...</p></div>;
  }
  if (estado !== 'autenticado') return <Login errorSesion={errorSesion} />;
  return <Dashboard nombreAdmin={admin.nombre || admin.email || 'Usuario Microsoft'} handleLogout={cerrar} />;
}

// Al salir del estado autenticado se desmonta todo el árbol sensible, incluidos
// cartera, selección, métricas, resultados y solicitudes de la sesión anterior.
function Dashboard({ nombreAdmin, handleLogout }) {
  const { seccionesRef, inicioRef, seccionActiva, navegar } = useNavegacionSecciones(true);
  const [errorMetricas, setErrorMetricas] = useState('');

  const [metricas, setMetricas] = useState({
    deudoresActivos: '-',
    carteraVencida: '$-',
    estrategiasIA: '-',
    recuperacion: '-%',
  });

  const [clienteId, setClienteId] = useState('');
  const [seleccionado, setSeleccionado] = useState(null);
  const [clienteSeleccionado, setClienteSeleccionado] = useState(null);
  const [cargandoDetalle, setCargandoDetalle] = useState(false);
  const solicitudDetalle = useRef(0);
  const [filtros, setFiltros] = useState({ query: '', segmento: '', analizado: '', estatus_deuda: '', orden: 'prioridad' });
  const [busqueda, setBusqueda] = useState('orden=prioridad');
  const [errorStatus, setErrorStatus] = useState('');

  const [cartera, setCartera] = useState([]);
  const [cargandoCartera, setCargandoCartera] = useState(false);
  const [errorCartera, setErrorCartera] = useState('');
  const solicitudCartera = useRef(0);
  const fichaRef = useRef(null);
  const [aperturaFicha, setAperturaFicha] = useState(0);
  async function abrirFicha(id) {
    const numeroId = Number(id);
    if (!Number.isInteger(numeroId) || numeroId < 1) { setErrorStatus('Ingresa un ID de cliente válido.'); return; }
    const solicitud = ++solicitudDetalle.current;
    setErrorStatus(''); setCargandoDetalle(true);
    try {
      const res = await apiFetch(`/api/clientes/${numeroId}`);
      if (!res.ok) throw new Error('No se pudo consultar el cliente.');
      const detalle = await res.json();
      if (solicitud !== solicitudDetalle.current) return;
      setClienteId(numeroId);
      setSeleccionado(numeroId);
      setClienteSeleccionado(detalle);
      setAperturaFicha(v => v + 1);
    } catch (error) {
      if (solicitud === solicitudDetalle.current) setErrorStatus(error.message);
    } finally {
      if (solicitud === solicitudDetalle.current) setCargandoDetalle(false);
    }
  }
  async function refrescarDetalle(id) {
    const solicitud = solicitudDetalle.current;
    const res = await apiFetch(`/api/clientes/${id}`);
    if (!res.ok) throw new Error('No se pudo actualizar el detalle. Consulta nuevamente el cliente.');
    const detalle = await res.json();
    if (solicitud === solicitudDetalle.current) {
      setClienteSeleccionado(actual => actual?.cliente_id === id ? detalle : actual);
    }
  }
  useEffect(() => {
    if (!aperturaFicha) return;
    navegar('operacion', true, false);
    fichaRef.current?.focus({ preventScroll: true });
  }, [aperturaFicha, navegar]);

  const cargarMetricas = useCallback(async () => {
    setErrorMetricas('');
    try {
      const response = await apiFetch('/api/metricas');
      if (!response.ok) throw new Error('Métricas no disponibles');
      if (response.ok) {
        const data = await response.json();
        setMetricas({
          deudoresActivos: data.deudores_activos,
          carteraVencida: `$${data.cartera_vencida.toLocaleString('es-MX')}`,
          estrategiasIA: data.estrategias_ia,
          recuperacion: `${data.porcentaje_recuperacion}%`,
          sinEvaluar: data.clientes_sin_evaluar,
        });
      }
    } catch (error) {
      console.error('Error al cargar métricas', error);
      setErrorMetricas('No se pudieron cargar las métricas.');
    }
  }, []);

  const cargarCartera = useCallback(async () => {
    const solicitud = ++solicitudCartera.current;
    setCargandoCartera(true);
    setErrorCartera('');
    try {
      const response = await apiFetch(`/api/clientes?solo_con_deuda=true&${busqueda}`);
      if (response.ok) {
        const data = await response.json();
        if (solicitud === solicitudCartera.current) setCartera(data);
      } else if (response.status !== 401 && solicitud === solicitudCartera.current) {
        setErrorCartera('No se pudo cargar la cartera priorizada.');
      }
    } catch (error) {
      console.error('Error al cargar cartera priorizada', error);
      if (solicitud === solicitudCartera.current) setErrorCartera('Error de conexión al cargar la cartera.');
    } finally {
      if (solicitud === solicitudCartera.current) setCargandoCartera(false);
    }
  }, [busqueda]);

  useEffect(() => {
    cargarMetricas();
    cargarCartera();
  }, [cargarMetricas, cargarCartera]);

  return (
    <div ref={inicioRef} className="dashboard">
      <aside className="sidebar">
        <div className="marca">PluriOne<span>Gestión de cartera</span></div>
        <nav aria-label="Navegación principal">
          {SECCIONES.map(({ id, titulo }) => (
            <a key={id} className={`nav-item${seccionActiva === id ? ' active' : ''}`}
              href={`#${id}`} aria-current={seccionActiva === id ? 'location' : undefined}
              onClick={(event) => {
                if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
                event.preventDefault();
                navegar(id, true, true);
              }}>
              <Icono nombre={id} />{titulo}
            </a>
          ))}
        </nav>
        <div className="sesion-admin">
          <small>Usuario autenticado</small>
          <span className="usuario-sesion"><Icono nombre="usuario" />{nombreAdmin || 'Administrador'}</span>
          <button className="btn-secundario" onClick={handleLogout}><Icono nombre="salir" />Cerrar sesión</button>
        </div>
      </aside>

      <main className="contenido-principal">
        <header className="barra-superior">
          <h1>Motor Inteligente de Cobranza</h1>
          <p>Administración y seguimiento de cartera · PluriOne</p>
        </header>

        <section ref={node => { seccionesRef.current.resumen = node; }} tabIndex={-1} id="resumen" className="header-dashboard" aria-labelledby="titulo-resumen">
          <p className="etiqueta-seccion">Visión general</p>
          <h2 id="titulo-resumen">Resumen de cartera</h2>
          {errorMetricas && <p role="alert" className="mensaje-error">{errorMetricas}</p>}
          <div className="grid-metricas">
            <div className="tarjeta-metrica"><h3>Deudores activos</h3><div className="valor">{metricas.deudoresActivos}</div></div>
            <div className="tarjeta-metrica"><h3>Saldo vencido</h3><div className="valor">{metricas.carteraVencida}</div></div>
            <div className="tarjeta-metrica"><h3>Clientes con estrategia IA</h3><div className="valor">{metricas.estrategiasIA}</div></div>
            <div className="tarjeta-metrica"><h3>Clientes sin evaluar</h3><div className="valor">{metricas.sinEvaluar ?? '-'}</div></div>
            <div className="tarjeta-metrica"><h3>Recuperación</h3><div className="valor">{metricas.recuperacion}</div></div>
          </div>
        </section>

        <section ref={node => { seccionesRef.current.operacion = node; }} tabIndex={-1} id="operacion" aria-labelledby="titulo-operacion">
          <p className="etiqueta-seccion">Gestión individual</p>
          <h2 id="titulo-operacion">Operación de Cobranza</h2>
          <div className="grid-operacion">
            <div className="panel-grid selector-cliente">
              <header className="encabezado-selector">
                <h3>Seleccionar cliente</h3>
                <p className="texto-secundario">Selecciona una fila de la cartera o consulta un cliente por ID.</p>
              </header>
              <form onSubmit={e => { e.preventDefault(); abrirFicha(clienteId); }}>
                <label htmlFor="cliente-operacion">ID del cliente</label>
                <div className="input-group">
                  <input id="cliente-operacion" type="number" value={clienteId} onChange={e => setClienteId(e.target.value)} min="1" required />
                  <button disabled={cargandoDetalle}>{cargandoDetalle ? 'Consultando...' : 'Consultar cliente'}</button>
                </div>
              </form>
              {errorStatus && <p className="mensaje-error" role="alert">{errorStatus}</p>}
              <div className="contexto-selector"><Icono nombre="cartera" /><p>La ficha reúne el saldo, el riesgo y la última estrategia del cliente. Los pagos y las comunicaciones se consultan en sus apartados.</p></div>
            </div>
            <div id="resultado-analisis" className="panel-grid" ref={fichaRef} tabIndex={-1} aria-labelledby="titulo-resultado">
              <h3 id="titulo-resultado">Resultado del análisis</h3>
              {clienteSeleccionado ? <FichaCliente key={clienteSeleccionado.cliente_id} detalle={clienteSeleccionado}
                alRefrescar={() => refrescarDetalle(clienteSeleccionado.cliente_id)}
                alActualizar={async () => { await Promise.all([refrescarDetalle(clienteSeleccionado.cliente_id), cargarMetricas(), cargarCartera()]); }} />
                : <div className="resultado-vacio"><Icono nombre="usuario" /><p className="texto-secundario">Selecciona un cliente de la cartera o introduce su ID.</p></div>}
            </div>
          </div>
        </section>

        <section ref={node => { seccionesRef.current.cartera = node; }} tabIndex={-1} id="cartera" className="panel-grid panel-cartera" aria-labelledby="titulo-cartera">
          <div className="encabezado-cartera">
            <div>
              <h2 id="titulo-cartera">Cartera priorizada</h2>
              <p className="texto-secundario">Ordenada por riesgo financiero (score de riesgo × monto pendiente).</p>
            </div>
            <button className="btn-secundario" onClick={cargarCartera} disabled={cargandoCartera}><Icono nombre="actualizar" />{cargandoCartera ? 'Actualizando...' : 'Actualizar'}</button>
          </div>
          <EvaluarCartera alEvaluar={async () => {
            await Promise.all([cargarCartera(), cargarMetricas(),
              ...(clienteSeleccionado ? [refrescarDetalle(clienteSeleccionado.cliente_id)] : [])]);
          }} />
          <form className="filtros-cartera" onSubmit={e => { e.preventDefault(); setBusqueda(new URLSearchParams(Object.entries(filtros).filter(([, v]) => v !== '')).toString()); }}>
            <label>Buscar cliente<input value={filtros.query} placeholder="Nombre, apellido, ID o folio" onChange={e => setFiltros({ ...filtros, query: e.target.value })} /></label>
            <label>Riesgo<select value={filtros.segmento} onChange={e => setFiltros({ ...filtros, segmento: e.target.value })}>
              <option value="">Todos</option>{Object.entries(SEGMENTO_INFO).map(([valor, info]) => <option key={valor} value={valor}>{info.label}</option>)}
            </select></label>
            <label>Análisis<select value={filtros.analizado} onChange={e => setFiltros({ ...filtros, analizado: e.target.value })}><option value="">Todos</option><option value="true">Evaluados</option><option value="false">Sin evaluar</option></select></label>
            <label>Estado de deuda<select value={filtros.estatus_deuda} onChange={e => setFiltros({ ...filtros, estatus_deuda: e.target.value })}><option value="">Todos</option>{['Pendiente', 'En Mora', 'Pagada'].map(v => <option key={v}>{v}</option>)}</select></label>
            <label>Orden<select value={filtros.orden} onChange={e => setFiltros({ ...filtros, orden: e.target.value })}>{[['prioridad', 'Mayor prioridad'], ['saldo', 'Mayor saldo'], ['atraso', 'Mayor atraso'], ['vencimiento', 'Vencimiento más próximo'], ['nombre', 'Nombre']].map(([v, texto]) => <option key={v} value={v}>{texto}</option>)}</select></label>
            <button>Buscar / filtrar</button>
          </form>
          {cargandoDetalle && <p role="status">Consultando cliente...</p>}
          {errorStatus && <p className="mensaje-error" role="alert">{errorStatus}</p>}
          {errorCartera && <div className="mensaje-error">{errorCartera}</div>}
          {!errorCartera && cartera.length === 0 && !cargandoCartera && <p className="texto-secundario">No hay clientes que coincidan con los filtros.</p>}
          {cartera.length > 0 && (
            <div className="tabla-wrapper" tabIndex="0" role="region" aria-label="Cartera priorizada">
              <table className="tabla-cartera">
                <thead><tr><th scope="col">Folio</th><th scope="col">Cliente</th><th scope="col" className="numero">Monto pendiente</th><th scope="col">Vencimiento</th><th scope="col" className="numero">Días</th><th scope="col">Segmento</th><th scope="col" className="numero">Score</th><th scope="col" className="numero">Prioridad</th></tr></thead>
                <tbody>
                  {cartera.map((c) => (
                    <tr key={c.cliente_id} className={`fila-cliente${seleccionado === c.cliente_id ? ' seleccionada' : ''}`} tabIndex={0} role="button" aria-label={`Seleccionar ${c.folio} · ${c.cliente_nombre}`}
                      aria-controls="resultado-analisis" aria-pressed={seleccionado === c.cliente_id}
                      onClick={() => abrirFicha(c.cliente_id)}
                      onKeyDown={e => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          if (!e.repeat) abrirFicha(c.cliente_id);
                        }
                      }}>
                      <td>{c.folio}</td><td>{c.cliente_nombre}</td>
                      <td className="numero">${c.monto_pendiente.toLocaleString('es-MX')}</td>
                      <td>{fechaVisible(c.fecha_vencimiento)}</td><td className="numero">{diasVisible(c.dias_restantes)}</td>
                      <td><BadgeSegmento segmento={c.segmento} /></td>
                      <td className="numero">{c.score_riesgo == null ? 'Sin calcular' : c.score_riesgo.toFixed(3)}</td>
                      <td className="numero">{c.prioridad.toLocaleString('es-MX')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
        <Analitica referenciaSeccion={node => { seccionesRef.current.analitica = node; }} />
        <Historial referenciaSeccion={node => { seccionesRef.current.historial = node; }} />
      </main>
    </div>
  );
}

export default App;
