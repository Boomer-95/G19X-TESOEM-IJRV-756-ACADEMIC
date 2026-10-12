import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { MsalProvider } from '@azure/msal-react';
import { msalInstance } from './auth/msalConfig';
import './index.css';
import App from './App.jsx';
import Login from './Login.jsx';
import ErrorBoundary from './ErrorBoundary.jsx';

const root = createRoot(document.getElementById('root'));
root.render(<ErrorBoundary>{msalInstance ? <StrictMode><MsalProvider instance={msalInstance}><App /></MsalProvider></StrictMode>
  : <Login configurado={false} />}</ErrorBoundary>);
