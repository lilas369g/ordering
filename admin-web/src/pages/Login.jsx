import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api, { TOKEN_KEY } from '../services/api'

export default function Login() {
  const navigate = useNavigate()
  const [phone, setPhone] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      // NOTE: using the customer login endpoint for now.
      // Swap to the employee login endpoint once it exists.
      const { data } = await api.post('/api/v1/customer/auth/login/', {
        phone_number: phone,
        password,
      })
      // Backend returns { access, refresh, user_type, is_phone_verified }.
      localStorage.setItem(TOKEN_KEY, data.access)
      if (data.refresh) localStorage.setItem('admin_refresh', data.refresh)
      navigate('/dashboard', { replace: true })
    } catch (err) {
      const detail =
        err?.response?.data?.detail ||
        err?.response?.data?.non_field_errors?.[0] ||
        'Login failed. Check your phone number and password.'
      setError(detail)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="center-screen">
      <div className="card" style={{ width: 380, padding: 32 }}>
        <div style={{ textAlign: 'center', marginBottom: 26 }}>
          <div
            style={{
              width: 54,
              height: 54,
              margin: '0 auto 14px',
              borderRadius: 14,
              display: 'grid',
              placeItems: 'center',
              fontSize: 26,
              background: 'linear-gradient(135deg, var(--accent), var(--accent-hover))',
            }}
          >
            ◆
          </div>
          <h1 style={{ fontSize: 22 }}>Ordering Admin</h1>
          <p className="muted" style={{ marginTop: 6, fontSize: 13 }}>
            Sign in to your dashboard
          </p>
        </div>

        <form onSubmit={submit}>
          <label className="muted" style={{ fontSize: 13 }}>
            Phone number
          </label>
          <input
            className="input"
            style={{ width: '100%', margin: '6px 0 16px' }}
            type="text"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="09xxxxxxxx"
            autoFocus
            required
          />

          <label className="muted" style={{ fontSize: 13 }}>
            Password
          </label>
          <input
            className="input"
            style={{ width: '100%', margin: '6px 0 16px' }}
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            required
          />

          {error && (
            <div
              style={{
                background: 'rgba(239,68,68,0.12)',
                color: 'var(--danger)',
                borderRadius: 8,
                padding: '10px 12px',
                fontSize: 13,
                marginBottom: 16,
              }}
            >
              {error}
            </div>
          )}

          <button className="btn" style={{ width: '100%' }} type="submit" disabled={loading}>
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  )
}
