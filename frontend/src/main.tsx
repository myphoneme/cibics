import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';

import App from './App';
import { AuthProvider } from './auth/AuthContext';
import { ToastProvider } from './components/ToastProvider';
import './styles.css';

const THEME_KEY = 'cibics_theme';
const savedTheme = localStorage.getItem(THEME_KEY);
const initialTheme = savedTheme === 'light' ? 'light' : 'dark';
document.documentElement.setAttribute('data-theme', initialTheme);

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ToastProvider>
        <AuthProvider>
          <App />
        </AuthProvider>
      </ToastProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
