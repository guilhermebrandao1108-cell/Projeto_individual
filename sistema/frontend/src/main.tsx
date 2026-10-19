import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { ApiError } from './api/client'
import App from './App'
import { AuthProvider } from './auth/AuthContext'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    // Client errors (403, 404, 409) are final: retrying would only repeat them.
    queries: { retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2, staleTime: 15_000 },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
