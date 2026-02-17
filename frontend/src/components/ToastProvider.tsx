import { createContext, useCallback, useContext, useMemo, useState } from 'react';

type ToastType = 'success' | 'error' | 'info';

interface ToastItem {
  id: number;
  type: ToastType;
  message: string;
}

interface ToastContextShape {
  showToast: (message: string, type?: ToastType, durationMs?: number) => void;
  success: (message: string, durationMs?: number) => void;
  error: (message: string, durationMs?: number) => void;
  info: (message: string, durationMs?: number) => void;
}

const ToastContext = createContext<ToastContextShape | undefined>(undefined);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const removeToast = useCallback((id: number) => {
    setToasts((current) => current.filter((item) => item.id !== id));
  }, []);

  const showToast = useCallback(
    (message: string, type: ToastType = 'info', durationMs = 3500) => {
      const id = Date.now() + Math.floor(Math.random() * 10000);
      setToasts((current) => [...current.slice(-3), { id, type, message }]);
      window.setTimeout(() => removeToast(id), durationMs);
    },
    [removeToast],
  );

  const value = useMemo<ToastContextShape>(
    () => ({
      showToast,
      success: (message: string, durationMs?: number) => showToast(message, 'success', durationMs),
      error: (message: string, durationMs?: number) => showToast(message, 'error', durationMs),
      info: (message: string, durationMs?: number) => showToast(message, 'info', durationMs),
    }),
    [showToast],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-stack" aria-live="polite" aria-atomic="true">
        {toasts.map((item) => (
          <div key={item.id} className={`toast-item toast-${item.type}`}>
            <span>{item.message}</span>
            <button type="button" className="toast-close" onClick={() => removeToast(item.id)} aria-label="Close">
              x
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used inside ToastProvider');
  }
  return context;
}
