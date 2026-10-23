import { useEffect, useRef, useState } from 'react';
import { apiFetch } from './api';

const CANALES_SUGERIDOS = ['Email', 'SMS', 'WhatsApp'];
const CANALES_ENVIO = ['Email', 'SMS', 'WhatsApp', 'Llamada'];

function normalizarCanalSugerido(valor) {
  const candidato = typeof valor === 'object' ? valor?.canal : valor;
  return CANALES_SUGERIDOS.includes(candidato) ? candidato : '';
}

export default function Comunicacion({ resultado, alRegistrar, permitirEdicion = false, canalSugerido }) {
  const [mensaje, setMensaje] = useState(resultado.mensaje || '');
  const [canal, setCanal] = useState(normalizarCanalSugerido(canalSugerido));
  const [cargando, setCargando] = useState(false);
  const [estado, setEstado] = useState('');
  const [proveedores, setProveedores] = useState(null);
  const enCurso = useRef(false);
  useEffect(() => {
    setCanal(normalizarCanalSugerido(canalSugerido));
  }, [resultado?.clienteId, canalSugerido]);
  useEffect(() => {
    let activo = true;
    apiFetch('/api/integraciones/estado').then(res => {
      if (!res.ok) throw new Error();
      return res.json();
    }).then(data => { if (activo) setProveedores(data); })
      .catch(() => { if (activo) setEstado('No se pudo consultar el modo de envío. Recarga antes de enviar.'); });
    return () => { activo = false; };
  }, []);
  const canalValido = CANALES_ENVIO.includes(canal);
  const real = canalValido && proveedores?.[{ Email: 'sendgrid', SMS: 'twilio_sms', WhatsApp: 'twilio_whatsapp', Llamada: 'twilio_voice' }[canal]];
  async function registrar() {
    if (enCurso.current || !proveedores || !canalValido) return;
    enCurso.current = true;
    setCargando(true); setEstado('');
    try {
      const res = await apiFetch('/api/comunicaciones', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cliente_id: resultado.clienteId, estrategia_id: resultado.estrategiaId ?? null, canal, mensaje: permitirEdicion ? mensaje.trim() : resultado.mensaje }),
      });
      if (!res.ok) throw new Error();
      const data = await res.json();
      setEstado(data.estado === 'Fallido' ? 'El proveedor no confirmó el envío. Revisa el registro antes de reintentar.'
        : data.modo === 'simulado' ? 'Comunicación registrada en modo simulación'
          : data.provider === 'sendgrid' ? 'Correo aceptado por SendGrid; entrega aún no confirmada.'
            : 'Comunicación aceptada por Twilio; entrega aún no confirmada.');
      alRegistrar?.();
    } catch { setEstado('No se pudo confirmar la comunicación. Revisa el historial antes de reintentar.'); }
    finally { enCurso.current = false; setCargando(false); }
  }
  return <div className="comunicacion-form">
    <header className="encabezado-comunicacion">
      <h4>Registro de comunicación</h4>
      <p>Modo: {proveedores ? (real ? 'Real' : 'Simulado') : 'Consultando…'}</p>
    </header>
    {proveedores && !real && <p className="aviso-demo">Este canal se registrará en modo simulación.</p>}
    {permitirEdicion && <label>Mensaje de la comunicación
      <textarea disabled={cargando} value={mensaje} maxLength={10000} onChange={e => setMensaje(e.target.value)} />
    </label>}
    <div className="input-group">
      <label>Canal de comunicación
      <select disabled={cargando} aria-label="Canal de comunicación" value={canal} onChange={e => setCanal(e.target.value)}>
        <option value="">Selecciona un canal</option>
        {CANALES_ENVIO.map(c => <option key={c} value={c}>{c}</option>)}
      </select>
      </label>
      <button type="button" onClick={registrar} disabled={cargando || !proveedores || !canalValido || (permitirEdicion && !mensaje.trim())}>{cargando ? 'Enviando...' : 'Enviar comunicación'}</button>
    </div>
    <p role="status">{estado}</p>
  </div>;
}
