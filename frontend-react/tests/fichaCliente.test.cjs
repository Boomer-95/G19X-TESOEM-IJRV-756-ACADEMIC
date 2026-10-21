const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { transformSync } = require('esbuild');

function render(recomendacion, canalSugerido) {
  const llamadas = [];
  const react = {
    useState: value => [value, () => {}],
    createElement: (type, props, ...children) => ({ type, props, children }),
  };
  const module = { exports: {} };
  const code = transformSync(fs.readFileSync('src/FichaCliente.jsx', 'utf8'), {
    loader: 'jsx', format: 'cjs', jsxFactory: 'React.createElement', jsxFragment: 'React.Fragment',
  }).code;
  vm.runInNewContext(code, { module, exports: module.exports, React: react, require: name =>
    name === 'react' ? react : name === './api' ? { apiFetch: (...args) => llamadas.push(args) } :
    name === './fechas' ? { fechaVisible: () => 'Fecha', diasVisible: () => 'Días' } : {} });
  const tree = module.exports.default({ detalle: {
    cliente_id: 1, folio: 'CL-000001', cliente_nombre: 'Prueba', monto_pendiente: 2000,
    monto_original_total: 2000, deudas: [], pagos: [], comunicaciones: [],
    recomendacion_recuperacion: recomendacion, canal_sugerido: canalSugerido,
  } });
  return { tree, llamadas };
}
function texto(tree) {
  if (tree == null) return '';
  if (typeof tree !== 'object') return String(tree);
  return tree.children.flat(Infinity).map(texto).join(' ');
}
for (const humana of [true, false]) {
  test(`ficha muestra decisión backend y revisión humana=${humana} sin solicitudes`, () => {
    const { tree, llamadas } = render({ tipo: 'Decisión del backend', motivo: 'Motivo del backend',
      nivel_atencion: 'alta', requiere_revision_humana: humana });
    const contenido = texto(tree);
    assert.match(contenido, /Decisión del backend/);
    assert.match(contenido, /Motivo del backend/);
    assert.match(contenido, /Nivel de atención:.*alta/);
    assert.match(contenido, humana ? /Requiere revisión\/autorización humana/ : /No requiere revisión humana previa/);
    assert.match(contenido, /No modifica la deuda ni autoriza condiciones financieras/);
    assert.match(contenido, /No reemplaza la decisión humana/);
    assert.equal(llamadas.length, 0);
  });
}
test('ficha tolera una API sin recomendación', () => {
  assert.match(texto(render(null).tree), /Recomendación no disponible/);
});

for (const fuente of ['real', 'simulada', 'mixta']) {
  test(`canal sugerido, confianza y fuente ${fuente} visibles sin solicitudes`, () => {
    const { tree, llamadas } = render(null, { canal: 'WhatsApp', confianza: 'media',
      motivo: 'Existe 1 pago asociado temporalmente dentro de los siguientes 7 días.', fuente_evidencia: fuente });
    const contenido = texto(tree);
    assert.match(contenido, /Canal sugerido:.*WhatsApp/);
    assert.match(contenido, /Confianza de evidencia:.*media/);
    assert.match(contenido, /pago asociado temporalmente/);
    assert.match(contenido, /Esta asociación es observacional y no demuestra que el canal haya causado el pago/);
    if (fuente === 'simulada') assert.match(contenido, /Sugerencia basada en datos de demostración\/simulados/);
    if (fuente === 'mixta') assert.match(contenido, /evidencia mixta: datos reales y de demostración\/simulados/);
    assert.equal(llamadas.length, 0);
  });
}
for (const canal of [undefined, { canal: null, estado: 'Sin evidencia suficiente', confianza: 'insuficiente', motivo: 'Faltan contactos.' }]) {
  test(`canal insuficiente o backend anterior: ${canal === undefined ? 'ausente' : 'insuficiente'}`, () => {
    const contenido = texto(render(null, canal).tree);
    assert.match(contenido, /Canal sugerido:.*Sin evidencia suficiente/);
    assert.match(contenido, /Confianza de evidencia:.*insuficiente/);
    assert.match(contenido, /Esta asociación es observacional y no demuestra que el canal haya causado el pago/);
  });
}
