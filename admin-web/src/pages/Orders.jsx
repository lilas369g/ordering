import { useEffect, useMemo, useState } from 'react'
import api from '../services/api'

// Status → badge colour mapping (per spec).
const STATUS_STYLES = {
  pending: { bg: 'rgba(245,158,11,0.15)', fg: 'var(--warning)' },
  preparing: { bg: 'rgba(59,130,246,0.15)', fg: 'var(--info)' },
  go_out: { bg: 'rgba(249,115,22,0.15)', fg: '#f97316' },
  customer_received: { bg: 'rgba(168,85,247,0.15)', fg: '#a855f7' },
  complete: { bg: 'rgba(16,185,129,0.15)', fg: 'var(--success)' },
  cancelled: { bg: 'rgba(239,68,68,0.15)', fg: 'var(--danger)' },
}

const STATUSES = [
  'pending',
  'preparing',
  'go_out',
  'customer_received',
  'complete',
  'cancelled',
]

// Shared badge — also used on the Dashboard.
export function StatusBadge({ status }) {
  const s = STATUS_STYLES[status] || {
    bg: 'rgba(148,163,184,0.15)',
    fg: 'var(--text-secondary)',
  }
  return (
    <span className="badge" style={{ background: s.bg, color: s.fg }}>
      {String(status || 'unknown').replace(/_/g, ' ')}
    </span>
  )
}

function asList(data) {
  if (Array.isArray(data)) return data
  if (data && Array.isArray(data.results)) return data.results
  return []
}

export default function Orders() {
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [expanded, setExpanded] = useState(null)

  useEffect(() => {
    api
      .get('/api/v1/orders/')
      .then(({ data }) => setOrders(asList(data)))
      .catch(() => setError('Could not load orders.'))
      .finally(() => setLoading(false))
  }, [])

  const filtered = useMemo(
    () =>
      statusFilter === 'all'
        ? orders
        : orders.filter((o) => o.status === statusFilter),
    [orders, statusFilter]
  )

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Orders</h1>
          {/* NOTE: GET /api/v1/orders/ is scoped to the logged-in user on the
              backend, so this currently lists only that account's orders.
              Point at an admin "all orders" endpoint when available. */}
          <p className="page-subtitle">{filtered.length} order(s)</p>
        </div>
      </div>

      <div className="toolbar">
        <select
          className="select"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="all">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s.replace(/_/g, ' ')}
            </option>
          ))}
        </select>
      </div>

      <div className="card">
        {loading ? (
          <div style={{ display: 'grid', placeItems: 'center', padding: 40 }}>
            <div className="spinner" />
          </div>
        ) : error ? (
          <p style={{ color: 'var(--danger)' }}>{error}</p>
        ) : filtered.length === 0 ? (
          <div className="empty-state">
            <div className="big-icon">🧾</div>
            No orders match this filter.
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Customer</th>
                  <th>Total</th>
                  <th>Status</th>
                  <th>Province</th>
                  <th>Date</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((o) => (
                  <FragmentRow
                    key={o.id}
                    order={o}
                    open={expanded === o.id}
                    onToggle={() => setExpanded(expanded === o.id ? null : o.id)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

function FragmentRow({ order, open, onToggle }) {
  return (
    <>
      <tr className="clickable" onClick={onToggle}>
        <td>#{order.id}</td>
        <td>{order.customer_name || '—'}</td>
        <td>{order.total_amount}</td>
        <td>
          <StatusBadge status={order.status} />
        </td>
        <td className="muted">{order.province || '—'}</td>
        <td className="muted">
          {order.created_at ? new Date(order.created_at).toLocaleString() : '—'}
        </td>
      </tr>
      {open && (
        <tr>
          <td colSpan={6} style={{ background: 'var(--bg-secondary)' }}>
            <div style={{ padding: '6px 4px' }}>
              <div className="detail-row">
                <span className="k">Phone</span>
                <span>{order.phone_number || '—'}</span>
              </div>
              <div className="detail-row">
                <span className="k">Address</span>
                <span>{order.shipping_address || '—'}</span>
              </div>
              <h4 style={{ margin: '12px 0 8px', fontSize: 13 }}>Items</h4>
              {(order.items || []).length === 0 ? (
                <span className="muted">No items.</span>
              ) : (
                <table style={{ background: 'var(--bg-card)', borderRadius: 8 }}>
                  <thead>
                    <tr>
                      <th>SKU</th>
                      <th>Qty</th>
                      <th>Unit Price</th>
                    </tr>
                  </thead>
                  <tbody>
                    {order.items.map((it) => (
                      <tr key={it.id}>
                        <td>{it.sku}</td>
                        <td>{it.quantity}</td>
                        <td>{it.unit_price}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}
