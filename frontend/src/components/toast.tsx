import { createContext, use, useCallback, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

interface Toast {
  id: number
  message: string
  kind: 'success' | 'error'
}

type Notify = (message: string, kind?: Toast['kind']) => void

const ToastContext = createContext<Notify>(() => {})

let nextId = 1

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const notify = useCallback<Notify>((message, kind = 'success') => {
    const id = nextId++
    setToasts((current) => [...current, { id, message, kind }])
    window.setTimeout(() => {
      setToasts((current) => current.filter((toast) => toast.id !== id))
    }, 4500)
  }, [])

  const value = useMemo(() => notify, [notify])

  return (
    <ToastContext value={value}>
      {children}
      <div className="toasts" aria-live="polite">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast ${toast.kind}`} role="status">
            {toast.message}
          </div>
        ))}
      </div>
    </ToastContext>
  )
}

export function useToast() {
  return use(ToastContext)
}
