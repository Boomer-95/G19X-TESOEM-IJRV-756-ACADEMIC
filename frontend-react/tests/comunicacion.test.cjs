const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { transformSync } = require('esbuild');

// Ejecuta el componente real con un arnés de hooks y una API en memoria.
// No necesita navegador, credenciales ni conexiones de red.
function montar(apiFetch, estrategiaId = null, canalSugerido = undefined) {
  const slots = [];
  let cursor = 0;
  let propsActuales = {
    resultado: { clienteId: 1, estrategiaId, mensaje: 'Mensaje original' },
    canalSugerido,
  };
  let efectosPendientes = [];
  const react = {
    createElement: (type, props, ...children) => ({ type, props: props || {}, children }),
    useState(initial) {
      const index = cursor++;
      if (!(index in slots)) slots[index] = initial;
      return [slots[index], value => { slots[index] = value; }];
    },
    useRef(initial) {
      const index = cursor++;
      if (!(index in slots)) slots[index] = { current: initial };
      return slots[index];
    },
    useEffect(effect, deps) {
      const index = cursor++;
      const prevDeps = slots[index];
      const cambio = !(index in slots) || !deps || !prevDeps
        || deps.length !== prevDeps.length
        || deps.some((d, i) => !Object.is(d, prevDeps[i]));
      if (cambio) {
        slots[index] = deps;
        efectosPendientes.push(effect);
      }
    },
  };
  const filename = path.join(__dirname, '../src/Comunicacion.jsx');
  const code = transformSync(fs.readFileSync(filename, 'utf8'), {
    loader: 'jsx', format: 'cjs', jsx: 'transform', jsxFactory: 'React.createElement',
  }).code;
  const module = { exports: {} };
  vm.runInNewContext(code, {
    module, exports: module.exports, React: react,
    require(name) {
      if (name === 'react') return react;
      if (name === './api') return { apiFetch };
      throw new Error(`Import inesperado: ${name}`);
    },
  }, { filename });
  function render(nuevasProps) {
    if (nuevasProps) {
      propsActuales = {
        ...propsActuales,
        ...nuevasProps,
        resultado: nuevasProps.resultado
          ? { ...propsActuales.resultado, ...nuevasProps.resultado }
          : propsActuales.resultado,
      };
    }
    cursor = 0;
    efectosPendientes = [];
    let tree = module.exports.default(propsActuales);
    if (efectosPendientes.length > 0) {
      const porEjecutar = efectosPendientes;
      efectosPendientes = [];
      porEjecutar.forEach(effect => effect());
      cursor = 0;
      tree = module.exports.default(propsActuales);
    }
    return tree;
  }
  render();
  return render;
}

function buscar(node, type) {
  if (!node || typeof node !== 'object') return undefined;
  if (node.type === type) return node;
  return node.children?.flat(Infinity).map(child => buscar(child, type)).find(Boolean);
}

for (const falla of [false, true]) {
  test(`un clic y clics repetidos pendientes hacen un solo POST; fallo=${falla}`, async () => {
    const calls = [];
    let completar;
    const pendiente = new Promise(resolve => { completar = resolve; });
    const render = montar(async (url, options) => {
      if (url === '/api/integraciones/estado') {
        return { ok: true, json: async () => ({ twilio_sms: true }) };
      }
      calls.push({ url, options });
      return pendiente;
    });
    await new Promise(resolve => setImmediate(resolve));
    let tree = render();
    buscar(tree, 'select').props.onChange({ target: { value: 'SMS' } });
    tree = render();
    const button = buscar(tree, 'button');
    assert.equal(button.props.type, 'button');
    assert.equal(button.props.disabled, false);
    const solicitud = button.props.onClick();
    // Invocar incluso el handler anterior antes del siguiente render prueba
    // el bloqueo sin depender del momento en que React deshabilita el botón.
    await button.props.onClick();
    await button.props.onClick();
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, '/api/comunicaciones');
    assert.equal(calls[0].options.method, 'POST');
    assert.deepEqual(JSON.parse(calls[0].options.body), {
      cliente_id: 1, estrategia_id: null, canal: 'SMS', mensaje: 'Mensaje original',
    });
    tree = render();
    assert.equal(buscar(tree, 'button').props.disabled, true);
    assert.equal(buscar(tree, 'select').props.disabled, true);
    completar({ ok: !falla, json: async () => ({ modo: 'simulado' }) });
    await solicitud;
    tree = render();
    assert.equal(buscar(tree, 'button').props.disabled, false);
    assert.equal(calls.length, 1);
    await buscar(tree, 'button').props.onClick();
    assert.equal(calls.length, 2); // Un nuevo clic después de finalizar sí se permite.
  });
}

const casosEstado = [
  [{ canal: 'SMS', provider: 'twilio', provider_status: 'accepted', estado: 'Aceptado' }, 'SMS · Aceptado por proveedor; entrega no confirmada'],
  [{ canal: 'SMS', provider: 'twilio', estado: 'Enviado' }, 'SMS · Aceptado por proveedor; entrega no confirmada'],
  [{ canal: 'SMS', provider: 'twilio', provider_status: 'delivered' }, 'SMS · Entregado'],
  [{ canal: 'WhatsApp', provider: 'twilio', provider_status: 'read' }, 'WhatsApp · Leído'],
  [{ canal: 'WhatsApp', provider: 'twilio', provider_status: 'failed' }, 'WhatsApp · Fallido'],
  [{ canal: 'SMS', provider: 'twilio', provider_status: 'undelivered' }, 'SMS · No entregado'],
  [{ canal: 'SMS', provider: 'twilio', provider_status: 'sent' }, 'SMS · Enviado; entrega no confirmada'],
  [{ canal: 'Email', provider: 'sendgrid', estado: 'Enviado' }, 'Email · Enviado (aceptado; entrega no confirmada)'],
  [{ canal: 'SMS', modo: 'simulado', estado: 'Simulado' }, 'SMS · Simulado'],
  [{ canal: 'Email' }, 'Email · Histórico; entrega no verificada'],
];
for (const [registro, esperado] of casosEstado) {
  test(`historial: ${esperado}`, async () => {
    const { estadoComunicacion } = await import('../src/estadoComunicacion.js');
    assert.equal(estadoComunicacion(registro), esperado);
  });
}


test('envío de una estrategia existente conserva su identificador', async () => {
  let cuerpo;
  const render = montar(async (url, options) => {
    if (url === '/api/integraciones/estado') return { ok: true, json: async () => ({ sendgrid: false }) };
    cuerpo = JSON.parse(options.body);
    return { ok: true, json: async () => ({ modo: 'simulado' }) };
  }, 42, 'Email');
  await new Promise(resolve => setImmediate(resolve));
  await buscar(render(), 'button').props.onClick();
  assert.equal(cuerpo.estrategia_id, 42);
  assert.equal(cuerpo.cliente_id, 1);
  assert.equal(cuerpo.canal, 'Email');
});

test('preselecciona canalSugerido SMS y WhatsApp al montar y permite cambiarlo manualmente', async () => {
  const renderSms = montar(async () => ({ ok: true, json: async () => ({ twilio_sms: true }) }), null, 'SMS');
  await new Promise(resolve => setImmediate(resolve));
  let treeSms = renderSms();
  assert.equal(buscar(treeSms, 'select').props.value, 'SMS');

  const renderWa = montar(async () => ({ ok: true, json: async () => ({ twilio_whatsapp: true }) }), null, 'WhatsApp');
  await new Promise(resolve => setImmediate(resolve));
  let treeWa = renderWa();
  const selectWa = buscar(treeWa, 'select');
  assert.equal(selectWa.props.value, 'WhatsApp');

  selectWa.props.onChange({ target: { value: 'Llamada' } });
  treeWa = renderWa();
  assert.equal(buscar(treeWa, 'select').props.value, 'Llamada');
});

test('sin canal sugerido inicia en opción neutral Selecciona un canal y bloquea el envío hasta elegir uno válido', async () => {
  const calls = [];
  const render = montar(async (url, options) => {
    if (url === '/api/integraciones/estado') return { ok: true, json: async () => ({ sendgrid: true }) };
    calls.push({ url, options });
    return { ok: true, json: async () => ({ modo: 'simulado' }) };
  }, null, null);
  await new Promise(resolve => setImmediate(resolve));
  let tree = render();
  const select = buscar(tree, 'select');
  const opciones = select.children.flat(Infinity);
  assert.equal(select.props.value, '');
  assert.equal(opciones[0].props.value, '');
  assert.equal(opciones[0].children[0], 'Selecciona un canal');

  const button = buscar(tree, 'button');
  assert.equal(button.props.disabled, true);
  await button.props.onClick();
  assert.equal(calls.length, 0);

  select.props.onChange({ target: { value: 'Email' } });
  tree = render();
  assert.equal(buscar(tree, 'button').props.disabled, false);
  await buscar(tree, 'button').props.onClick();
  assert.equal(calls.length, 1);
  assert.equal(JSON.parse(calls[0].options.body).canal, 'Email');
});

test('al cambiar entre clientes sincroniza el canal y vuelve a opción neutral cuando no hay evidencia', async () => {
  const render = montar(async () => ({ ok: true, json: async () => ({ twilio_sms: true }) }), null, 'SMS');
  await new Promise(resolve => setImmediate(resolve));
  let tree = render();
  assert.equal(buscar(tree, 'select').props.value, 'SMS');

  tree = render({ resultado: { clienteId: 2 }, canalSugerido: 'WhatsApp' });
  assert.equal(buscar(tree, 'select').props.value, 'WhatsApp');

  tree = render({ resultado: { clienteId: 3 }, canalSugerido: null });
  assert.equal(buscar(tree, 'select').props.value, '');
  assert.equal(buscar(tree, 'button').props.disabled, true);
});
