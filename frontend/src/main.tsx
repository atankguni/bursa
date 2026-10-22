import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { AuthProvider } from './lib/auth'
import { SettingsProvider } from './lib/settings'
import './index.css'
import { errorStatus } from './api/client'

// Single shared React Query client. Polling is opt-in per query (see the
// Home/Watchlist pages) so unfocused or static queries don't hit the API.
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      // Retry once on network/server errors; never on 401/403/404, which won't
      // change by asking again (401 sends the app back to sign-in).
      retry: (failureCount, error) => {
        const status = errorStatus(error)
        return failureCount < 1 && !(status && status >= 400 && status < 500)
      },
      refetchOnWindowFocus: false,
    },
  },
})

const root = document.getElementById('root')
if (!root) throw new Error('index.html has no #root element')
ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <SettingsProvider>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </SettingsProvider>
      </AuthProvider>
    </QueryClientProvider>
  </React.StrictMode>,
)
