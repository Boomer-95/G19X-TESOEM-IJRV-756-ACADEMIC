import { Component } from 'react';

export default class ErrorBoundary extends Component {
  state = { fallo: false };

  static getDerivedStateFromError() {
    return { fallo: true };
  }

  render() {
    if (this.state.fallo) {
      return <div className="login-wrapper"><div className="login-card" role="alert">
        <h1>PluriOne</h1>
        <p>Ocurrió un error inesperado en la interfaz. Recarga la aplicación.</p>
      </div></div>;
    }
    return this.props.children;
  }
}
