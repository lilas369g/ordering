import { Navigate } from 'react-router-dom'
import { TOKEN_KEY } from '../services/api'

// Gate for authenticated routes: no token in localStorage → send to /login.
export default function ProtectedRoute({ children }) {
  const token = localStorage.getItem(TOKEN_KEY)
  if (!token) {
    return <Navigate to="/login" replace />
  }
  return children
}
