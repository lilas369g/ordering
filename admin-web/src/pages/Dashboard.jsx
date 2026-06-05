import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../services/api'
import { BoxIcon, ListIcon, UsersIcon, WarehouseIcon } from '../components/icons'
import { StatusBadge } from './Orders'

// Normalises either a plain array or a DRF paginated {results:[...]} response.
function asList(data) {
  if (Array.isArray(data)) return data
  if (data && Array.isArray(data.results)) return data.results
  return []
}

export default function Dashboard() {
  const [products, setProducts] = useState([])
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    Promise.allSettled([
      api.get('/api/v1/catalog/products/'),
      api.get('/api/v1/orders/'),
    ]).then(([p, o]) => {
      if (!alive) return
      if (p.status === 'fulfilled') setProducts(asList(p.value.data))
      if (o.status === 'fulfilled') setOrders(asList(o.value.data))
      setLoading(false)
    })
    return () => {
      alive = false
    }
  }, [])

  // Count variants flagged with a low available quantity.
  const lowStock = products.reduce((acc, prod) => {
    const lows = (prod.variants || []).filter(
      (v) => typeof v.available_quantity === 'number' && v.available_quantity <= 5
    )
    return acc + lows.length
  }, 0)

  // NOTE: there is no dedicated customers-count endpoint yet, so we derive a
  // rough figure from distinct phone numbers seen on orders. Replace with a real
  // GET /api/v1/admin/customers/ count when that endpoint lands.
  const customerCount = new Set(
    orders.map((o) => o.phone_number).filter(Boolean)
  ).size

  const stats = [
    { label: 'Total Products', value: products.length, Icon: BoxIcon },
    { label: 'Total Orders', value: orders.length, Icon: ListIcon },
    { label: 'Total Customers', value: customerCount || '—', Icon: UsersIcon },
    { label: 'Low Stock Items', value: lowStock, Icon: WarehouseIcon },
  ]

  const recent = [...orders]
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
    .slice(0, 5)

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle">Overview of your store</p>
        </div>
      </div>

      {loading ? (
        <div style={{ display: 'grid', placeItems: 'center', padding: 60 }}>
          <div className="spinner" />
        </div>
      ) : (
        <>
          <div
            className="grid"
            style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', marginBottom: 24 }}
          >
            {stats.map(({ label, value, Icon }) => (
              <div className="stat-card" key={label}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div className="stat-label">{label}</div>
                  <div className="stat-icon">
                    <Icon width={18} height={18} />
                  </div>
                </div>
                <div className="stat-value">{value}</div>
              </div>
            ))}
          </div>

          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 14 }}>
              <h3 className="section-title" style={{ marginBottom: 0 }}>
                Recent Orders
              </h3>
              <Link to="/orders" className="muted" style={{ fontSize: 13 }}>
                View all →
              </Link>
            </div>

            {recent.length === 0 ? (
              <p className="muted" style={{ padding: '14px 0' }}>
                No orders to show yet.
              </p>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Customer</th>
                      <th>Total</th>
                      <th>Status</th>
                      <th>Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recent.map((o) => (
                      <tr key={o.id}>
                        <td>#{o.id}</td>
                        <td>{o.customer_name || '—'}</td>
                        <td>{o.total_amount}</td>
                        <td>
                          <StatusBadge status={o.status} />
                        </td>
                        <td className="muted">
                          {o.created_at ? new Date(o.created_at).toLocaleDateString() : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
