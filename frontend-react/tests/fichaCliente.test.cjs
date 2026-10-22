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
    const motivo = 'Atraso de 30 a 89 días y saldo mayor a $1,000 MXN. Las opciones calculadas son propuestas informativas sujetas a revisión y autorización humana; no modifican la deuda ni constituyen un acuerdo aprobado.';
    const { tree, llamadas } = render({ tipo: 'Propuesta de plan de pagos', motivo,
      nivel_atencion: 'alta', requiere_revision_humana: humana });
    const contenido = texto(tree);
    assert.match(contenido, /Propuesta de plan de pagos/);
    assert.match(contenido, /Las opciones calculadas son propuestas informativas sujetas a revisión y autorización humana/);
    assert.match(contenido, /Nivel de atención:.*alta/);
    assert.match(contenido, humana ? /Requiere revisión\/autorización humana/ : /No requiere revisión humana previa/);
    assert.match(contenido, /No modifica la deuda ni autoriza condiciones financieras/);
    assert.match(contenido, /No reemplaza la decisión humana/);
    assert.equal(llamadas.length, 0);
  });
}
test('ficha renderiza propuestas financieras cuando existen pronto pago y plan de pagos', () => {
  const { tree } = render({
    tipo: 'Propuesta de plan de pagos',
    motivo: 'Atraso de 30 a 89 días y saldo mayor a $1,000 MXN. Las opciones calculadas son propuestas informativas sujetas a revisión y autorización humana; no modifican la deuda ni constituyen un acuerdo aprobado.',
    nivel_atencion: 'alta',
    requiere_revision_humana: true,
    propuesta_pronto_pago: {
      porcentaje_descuento: 10.0,
      descuento: 600.0,
      saldo_propuesto: 5400.0,
      vigencia_dias: 5,
      advertencia: 'Propuesta sujeta a revisión y autorización humana. No modifica la deuda.',
    },
    propuesta_plan_pagos: {
      saldo_base: 6000.0,
      opciones: [
        { meses: 3, cuota_mensual: 2000.0 },
        { meses: 6, cuota_mensual: 1000.0 },
      ],
      advertencia: 'Propuesta sujeta a revisión y autorización humana. No modifica la deuda.',
    },
  });
  const contenido = texto(tree);
  assert.match(contenido, /10% de descuento/);
  assert.match(contenido, /Cuota mensual estimada de/);
  assert.match(contenido, /Propuesta sujeta a revisión y autorización humana\. No modifica la deuda\./);
});
test('ficha no renderiza elementos de propuesta cuando la recomendación no los contiene', () => {
  const { tree } = render({
    tipo: 'Recordatorio de pago',
    motivo: 'Saldo de hasta $1,000 MXN o atraso menor a 30 días; recordar el pago del saldo vigente.',
    nivel_atencion: 'normal',
    requiere_revision_humana: false,
  });
  const contenido = texto(tree);
  assert.doesNotMatch(contenido, /Cuota mensual estimada de/);
  assert.doesNotMatch(contenido, /Propuesta sujeta a revisión y autorización humana\. No modifica la deuda\./);
});
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
