import '@fontsource-variable/instrument-sans'
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/600.css'
import './styles/app.css'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { SWRConfig } from 'swr'
import App from './App'
import { ToastProvider } from './components/toast'
import { ApiError, fetcher } from './lib/api'
import { AuthProvider } from './lib/auth'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <SWRConfig
      value={{
        fetcher,
        // Client errors (403, 404…) won't fix themselves: don't retry them.
        shouldRetryOnError: (error) => !(error instanceof ApiError && error.status < 500),
      }}
    >
      <AuthProvider>
        <ToastProvider>
          <App />
        </ToastProvider>
      </AuthProvider>
    </SWRConfig>
  </StrictMode>,
)
