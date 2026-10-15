const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { transformSync } = require('esbuild');

function hooks() {
  const slots = [];
  let cursor = 0;
  const callbacks = [];
  return {
    callbacks,
    reset() { cursor = 0; callbacks.length = 0; },
    createElement: (type, props, ...children) => ({ type, props: props || {}, children }),
    useState(initial) {
      const i = cursor++;
      if (!(i in slots)) slots[i] = initial;
      return [slots[i], v => { slots[i] = typeof v === 'function' ? v(slots[i]) : v; }];
    },
    useRef(initial) {
      const i = cursor++;
      if (!(i in slots)) slots[i] = { current: initial };
      return slots[i];
    },
    useEffect() {},
    useCallback(fn) { callbacks.push(fn); return fn; },
  };
}

function cargar(archivo, react, imports, extra = '') {
  const filename = path.join(__dirname, '../src', archivo);
  const code = transformSync(fs.readFileSync(filename, 'utf8') + extra, {
    loader: 'jsx', format: 'cjs', jsxFactory: 'React.createElement',
  }).code;
  const module = { exports: {} };
  vm.runInNewContext(code, { module, exports: module.exports, React: react,
    URLSearchParams, console: { error() {} }, require(name) {
      if (name === 'react') return react;
      return imports[name] || { default: () => null };
    },
  }, { filename });
  return module.exports;
}

function buscar(node, condicion) {
  if (!node || typeof node !== 'object') return undefined;
  if (condicion(node)) return node;
  return node.children?.flat(Infinity).map(n => buscar(n, condicion)).find(Boolean);
}
function texto(node) {
  if (node == null || node === false) return '';
  if (typeof node !== 'object') return String(node);
  return node.children?.flat(Infinity).map(texto).join('') || '';
}

for (const fallo of ['ninguno', 'parcial', 'modelo', 'red']) {
  test(`evaluación predictiva: un POST, carga, resultado y refresco (${fallo})`, async () => {
    const react = hooks();
    const llamadas = [];
    let completar, rechazar, refrescos = 0;
    const pendiente = new Promise((resolve, reject) => { completar = resolve; rechazar = reject; });
    const Componente = cargar('EvaluarCartera.jsx', react, { './api': { apiFetch: (url, options) => {
      llamadas.push({ url, options }); return pendiente;
    } } }).default;
    function render() { react.reset(); return Componente({ alEvaluar: async () => { refrescos++; } }); }
    const boton = buscar(render(), n => n.type === 'button');
    assert.equal(boton.props.type, 'button');
    const solicitud = boton.props.onClick();
    await boton.props.onClick();
    assert.equal(llamadas.length, 1);
    assert.equal(llamadas[0].url, '/api/cartera/evaluar');
    assert.equal(llamadas[0].options.method, 'POST');
    assert.equal(buscar(render(), n => n.type === 'button').props.disabled, true);
    assert.match(texto(render()), /Evaluando cartera/);
    if (fallo === 'red') rechazar(new Error('Error de conexión'));
    else completar({ ok: fallo !== 'modelo', status: fallo === 'modelo' ? 503 : 200,
      json: async () => ({ clientes_activos_encontrados: 14, clientes_evaluados: fallo === 'parcial' ? 1 : 2,
        clientes_ya_evaluados_omitidos: 12, clientes_fallidos: fallo === 'parcial' ? 1 : 0,
        clientes_sin_deuda_omitidos: 0, errores: fallo === 'parcial' ? [{ cliente_id: 13 }] : [] }) });
    await solicitud;
    const tree = render();
    assert.equal(buscar(tree, n => n.type === 'button').props.disabled, false);
    assert.equal(refrescos, 1);
    assert.equal(llamadas.length, 1);
    if (fallo === 'ninguno' || fallo === 'parcial') {
      assert.match(texto(tree), /Activos encontrados: 14/);
      assert.match(texto(tree), /Ya evaluados omitidos: 12/);
      if (fallo === 'parcial') assert.match(texto(tree), /pendientes por error: 13/);
    } else assert.ok(buscar(tree, n => n.props.role === 'alert'));
    assert.match(texto(tree), /Calcula el riesgo predictivo/);
    assert.doesNotMatch(texto(tree), /Generar IA|Generando estrategia/);
  });
}

test('Dashboard refresca tabla y métricas al terminar; muestra score, badge y nueva prioridad', async () => {
  const react = hooks();
  const llamadas = [];
  let evaluada = false;
  function Evaluar() {}
  const App = cargar('App.jsx', react, {
    './EvaluarCartera': { __esModule: true, default: Evaluar },
    './useNavegacionSecciones': { __esModule: true, SECCIONES: [], default: () => ({
      seccionesRef: { current: {} }, inicioRef: {}, navegar() {},
    }) },
    './fechas': { fechaVisible: () => '-', diasVisible: () => '-' },
    './api': { apiFetch: async url => {
      llamadas.push(url);
      return { ok: true, json: async () => url === '/api/metricas'
        ? { deudores_activos: 1, cartera_vencida: 18600, estrategias_ia: 12, porcentaje_recuperacion: 0, clientes_sin_evaluar: evaluada ? 0 : 1 }
        : [{ cliente_id: 13, folio: 'CL-000013', cliente_nombre: 'Demo 13', monto_pendiente: 18600,
          score_riesgo: evaluada ? .28 : null, segmento: evaluada ? 'Bajo riesgo' : 'No definido',
          prioridad: evaluada ? 5208 : 0 }] };
    } },
  }, '\nexport { Dashboard };');
  function render() { react.reset(); return App.Dashboard({ nombreAdmin: 'Prueba', handleLogout() {} }); }
  render();
  await react.callbacks[1]();
  assert.match(texto(render()), /Sin calcular/);
  evaluada = true;
  await buscar(render(), n => n.type === Evaluar).props.alEvaluar();
  const tree = render();
  assert.ok(llamadas.includes('/api/metricas'));
  assert.equal(llamadas.filter(url => url.startsWith('/api/clientes?')).length, 2);
  assert.match(texto(tree), /0\.280/);
  assert.match(texto(tree), /5,208/);
  assert.ok(buscar(tree, n => n.props.segmento === 'Bajo riesgo'));
});

test('al finalizar usa el refresco más reciente y libera el botón aunque falle la vista', async () => {
  const react = hooks();
  let completar, antiguos = 0, recientes = 0;
  const pendiente = new Promise(resolve => { completar = resolve; });
  const Componente = cargar('EvaluarCartera.jsx', react, { './api': { apiFetch: () => pendiente } }).default;
  function render(callback) { react.reset(); return Componente({ alEvaluar: callback }); }
  const tree = render(async () => { antiguos++; });
  const solicitud = buscar(tree, n => n.type === 'button').props.onClick();
  const refrescar = async () => { recientes++; throw new Error('Vista'); };
  render(refrescar);
  completar({ ok: true, json: async () => ({ clientes_activos_encontrados: 0, clientes_evaluados: 0,
    clientes_ya_evaluados_omitidos: 0, clientes_fallidos: 0, errores: [] }) });
  await solicitud;
  assert.equal(antiguos, 0);
  assert.equal(recientes, 1);
  const final = render(refrescar);
  assert.equal(buscar(final, n => n.type === 'button').props.disabled, false);
  assert.match(texto(final), /Pulsa Actualizar/);
  assert.match(texto(final), /Activos encontrados: 0/);
});
