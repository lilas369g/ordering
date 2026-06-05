import { useEffect, useMemo, useState } from 'react'
import api from '../services/api'

const PAGE_SIZE = 10

function asList(data) {
  if (Array.isArray(data)) return data
  if (data && Array.isArray(data.results)) return data.results
  return []
}

export default function Products() {
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [search, setSearch] = useState('')
  const [activeFilter, setActiveFilter] = useState('all') // all | active | inactive
  const [page, setPage] = useState(1)
  const [showModal, setShowModal] = useState(false)

  useEffect(() => {
    api
      .get('/api/v1/catalog/products/')
      .then(({ data }) => setProducts(asList(data)))
      .catch(() => setError('Could not load products.'))
      .finally(() => setLoading(false))
  }, [])

  // Client-side search + is_active filter.
  const filtered = useMemo(() => {
    return products.filter((p) => {
      const matchesSearch = p.name?.toLowerCase().includes(search.toLowerCase())
      const matchesActive =
        activeFilter === 'all' ||
        (activeFilter === 'active' && p.is_active) ||
        (activeFilter === 'inactive' && !p.is_active)
      return matchesSearch && matchesActive
    })
  }, [products, search, activeFilter])

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const safePage = Math.min(page, totalPages)
  const pageItems = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE)

  // Reset to first page whenever filters change.
  useEffect(() => {
    setPage(1)
  }, [search, activeFilter])

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Products</h1>
          <p className="page-subtitle">{filtered.length} product(s)</p>
        </div>
        <button className="btn" onClick={() => setShowModal(true)}>
          + Add Product
        </button>
      </div>

      <div className="toolbar">
        <input
          className="input"
          style={{ minWidth: 260, flex: 1 }}
          placeholder="Search by name…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          className="select"
          value={activeFilter}
          onChange={(e) => setActiveFilter(e.target.value)}
        >
          <option value="all">All</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>
      </div>

      <div className="card">
        {loading ? (
          <div style={{ display: 'grid', placeItems: 'center', padding: 40 }}>
            <div className="spinner" />
          </div>
        ) : error ? (
          <p style={{ color: 'var(--danger)' }}>{error}</p>
        ) : pageItems.length === 0 ? (
          <div className="empty-state">
            <div className="big-icon">📦</div>
            No products match your filters.
          </div>
        ) : (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Name</th>
                    <th>Category</th>
                    <th>Brand</th>
                    <th>Variants</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {pageItems.map((p) => (
                    <tr key={p.id}>
                      <td>#{p.id}</td>
                      <td>{p.name}</td>
                      <td className="muted">{p.category?.name || '—'}</td>
                      <td className="muted">{p.brand?.name || '—'}</td>
                      <td>{p.variants?.length ?? 0}</td>
                      <td>
                        <span
                          className="badge"
                          style={{
                            background: p.is_active
                              ? 'rgba(16,185,129,0.15)'
                              : 'rgba(148,163,184,0.15)',
                            color: p.is_active ? 'var(--success)' : 'var(--text-secondary)',
                          }}
                        >
                          {p.is_active ? 'active' : 'inactive'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="pagination">
              <button
                className="page-btn"
                disabled={safePage <= 1}
                onClick={() => setPage((n) => n - 1)}
              >
                ‹
              </button>
              {Array.from({ length: totalPages }, (_, i) => i + 1).map((n) => (
                <button
                  key={n}
                  className={`page-btn${n === safePage ? ' active' : ''}`}
                  onClick={() => setPage(n)}
                >
                  {n}
                </button>
              ))}
              <button
                className="page-btn"
                disabled={safePage >= totalPages}
                onClick={() => setPage((n) => n + 1)}
              >
                ›
              </button>
            </div>
          </>
        )}
      </div>

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div style={{ fontSize: 40, marginBottom: 10 }}>🚧</div>
            <h3 style={{ marginBottom: 8 }}>Coming Soon</h3>
            <p className="muted" style={{ marginBottom: 20 }}>
              Product creation isn’t wired up yet.
            </p>
            <button className="btn" onClick={() => setShowModal(false)}>
              Got it
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
