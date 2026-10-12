const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const React = require('react');
const { transformSync } = require('esbuild');

test('boundary raíz protege ambos accesos y descarta el árbol ante un error sin mostrar detalles', () => {
  const module = { exports: {} };
  const code = transformSync(fs.readFileSync('src/ErrorBoundary.jsx', 'utf8'), {
    loader: 'jsx', format: 'cjs', jsxFactory: 'React.createElement',
  }).code;
  vm.runInNewContext(code, { module, exports: module.exports, React,
    require: name => { assert.equal(name, 'react'); return React; },
  });
  const Boundary = module.exports.default;
  const sensible = React.createElement('p', null, 'DATOS-SESION-FICTICIA');
  const boundary = new Boundary({ children: sensible });
  assert.equal(boundary.render(), sensible);
  boundary.state = Boundary.getDerivedStateFromError(new Error('STACK-PRIVADO-SENTINELA'));
  const fallback = boundary.render();
  const texto = elemento => elemento == null ? '' : typeof elemento !== 'object' ? String(elemento)
    : React.Children.toArray(elemento.props.children).map(texto).join(' ');
  assert.match(texto(fallback), /Ocurrió un error inesperado en la interfaz\. Recarga la aplicación\./);
  assert.doesNotMatch(texto(fallback), /STACK-PRIVADO|DATOS-SESION/);
  assert.equal(fallback.props.children.props.role, 'alert');

  const main = transformSync(fs.readFileSync('src/main.jsx', 'utf8'), {
    loader: 'jsx', format: 'cjs', jsxFactory: 'React.createElement',
  }).code;
  for (const configurado of [false, true]) {
    let root;
    const stubs = {
      react: React,
      'react-dom/client': { createRoot: () => ({ render: tree => { root = tree; } }) },
      '@azure/msal-react': { MsalProvider: () => null },
      './auth/msalConfig': { msalInstance: configurado ? {} : null },
      './ErrorBoundary.jsx': { __esModule: true, default: Boundary },
      './App.jsx': { __esModule: true, default: () => null },
      './Login.jsx': { __esModule: true, default: () => null }, './index.css': {},
    };
    vm.runInNewContext(main, { module: { exports: {} }, exports: {}, React,
      document: { getElementById: () => ({}) }, require: name => {
        assert.ok(Object.hasOwn(stubs, name)); return stubs[name];
      },
    });
    assert.equal(root.type, Boundary);
    assert.ok(root.props.children);
  }
});
