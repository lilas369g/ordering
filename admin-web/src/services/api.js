import axios from 'axios'

// Relative base URL: requests hit the same origin that serves the app, so they
// flow through the Vite dev proxy (→ Django on :8000, see vite.config.js) in
// development, or through Nginx when served behind it in production.
// All backend routes live under /api/v1/*.
export const API_BASE_URL = ''
export const TOKEN_KEY = 'admin_token'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

// Attach JWT to every request if present.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// On 401, drop the token and bounce to the login page.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      localStorage.removeItem(TOKEN_KEY)
      // Avoid redirect loop if the failing request *is* the login call.
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default api
