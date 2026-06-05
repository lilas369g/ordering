import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import { LockIcon, TrophyIcon } from '../components/icons'

// ---------------------------------------------------------------------------
// Session 5 — Load Balancing benchmark data (real numbers we collected).
// ---------------------------------------------------------------------------
const ALGORITHMS = [
  {
    key: 'round_robin',
    name: 'Round Robin',
    catalogMean: 2241,
    catalogP95: 2347,
    catalogMax: 3185,
    checkoutMean: 2848,
    checkoutP95: 3343,
    wallTime: 45.71,
  },
  {
    key: 'least_conn',
    name: 'Least Connections',
    catalogMean: 2228,
    catalogP95: 2333,
    catalogMax: 1958,
    checkoutMean: 2789,
    checkoutP95: 3178,
    wallTime: 45.07,
    active: true,
  },
  {
    key: 'ip_hash',
    name: 'IP Hash',
    catalogMean: 2213,
    catalogP95: null,
    catalogMax: null,
    checkoutMean: 2789,
    checkoutP95: 3548,
    wallTime: 44.98,
  },
  {
    key: 'weighted_rr',
    name: 'Weighted RR',
    catalogMean: 2218,
    catalogP95: null,
    catalogMax: null,
    checkoutMean: 2776,
    checkoutP95: 3235,
    wallTime: 45.15,
  },
]

const ACCENT = '#6366f1'
const BEST = '#10b981'
const WORST = '#ef4444'

// Highlight the best (or worst) bar so the takeaway is visually obvious.
function tintedBars(data, valueKey, { lowerIsBetter = true, markWorst = false }) {
  const vals = data.map((d) => d[valueKey]).filter((v) => v != null)
  const best = lowerIsBetter ? Math.min(...vals) : Math.max(...vals)
  const worst = lowerIsBetter ? Math.max(...vals) : Math.min(...vals)
  return data.map((d) => {
    let fill = ACCENT
    if (d[valueKey] === best) fill = BEST
    else if (markWorst && d[valueKey] === worst) fill = WORST
    return { ...d, fill }
  })
}

const tooltipStyle = {
  background: '#1a1d27',
  border: '1px solid #2d3148',
  borderRadius: 8,
  color: '#f1f5f9',
}

function ChartCard({ title, subtitle, data, valueKey, opts }) {
  const tinted = tintedBars(data, valueKey, opts)
  return (
    <div className="card">
      <h3 className="section-title" style={{ marginBottom: 2 }}>
        {title}
      </h3>
      <p className="page-subtitle" style={{ marginBottom: 14 }}>
        {subtitle}
      </p>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={tinted} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2d3148" vertical={false} />
          <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 12 }} />
          <YAxis tick={{ fill: '#94a3b8', fontSize: 12 }} unit="ms" />
          <Tooltip
            contentStyle={tooltipStyle}
            cursor={{ fill: 'rgba(99,102,241,0.08)' }}
            formatter={(v) => [`${v} ms`, title]}
          />
          <Bar dataKey={valueKey} radius={[6, 6, 0, 0]}>
            {tinted.map((entry, i) => (
              <Cell key={i} fill={entry.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

const SETUP = [
  { label: 'Load Balancer', value: 'Nginx 1.30.1' },
  { label: 'Workers', value: '3 × Waitress (threads=4)' },
  { label: 'Algorithm', value: 'Least Connections', active: true },
  { label: 'Database', value: 'PostgreSQL' },
]

const WINNERS = [
  { tag: 'Uniform workload', name: 'Round Robin' },
  { tag: 'Mixed workload (this project)', name: 'Least Connections', win: true },
  { tag: 'Session persistence', name: 'IP Hash' },
  { tag: 'Heterogeneous servers', name: 'Weighted Round Robin' },
]

const LOCKED = [
  {
    session: 'Session 6: Redis Caching',
    metric: 'Will show cache hit rate vs miss rate',
  },
  {
    session: 'Session 4: Batch ETL Performance',
    metric: 'Will show batch throughput & processing time',
  },
  {
    session: 'Session 7: Checkout Race Condition Results',
    metric: 'Will show concurrent-checkout consistency under load',
  },
  {
    session: 'Session 8: Distributed Tracing',
    metric: 'Will show span timings across services',
  },
]

function fmt(v) {
  return v == null ? '—' : v
}

export default function Performance() {
  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Performance</h1>
          <p className="page-subtitle">Load balancing benchmarks & algorithm comparison</p>
        </div>
      </div>

      {/* ---------- Section 1: Current Setup ---------- */}
      <h3 className="section-title">Current Setup</h3>
      <div
        className="grid"
        style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', marginBottom: 28 }}
      >
        {SETUP.map((s) => (
          <div className="stat-card" key={s.label}>
            <div className="stat-label">{s.label}</div>
            <div style={{ fontSize: 18, fontWeight: 700, marginTop: 8 }}>
              {s.value}
              {s.active && (
                <span
                  className="badge"
                  style={{
                    marginLeft: 8,
                    background: 'rgba(16,185,129,0.15)',
                    color: 'var(--success)',
                  }}
                >
                  active
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* ---------- Section 2: Algorithm Comparison ---------- */}
      <h3 className="section-title">Algorithm Comparison — Session 5: Load Balancing</h3>

      <div
        className="grid"
        style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', marginBottom: 16 }}
      >
        <ChartCard
          title="Catalog Mean Latency"
          subtitle="Lower is better · green = fastest"
          data={ALGORITHMS}
          valueKey="catalogMean"
          opts={{ lowerIsBetter: true }}
        />
        <ChartCard
          title="Checkout Mean Latency"
          subtitle="Lower is better · green = fastest"
          data={ALGORITHMS}
          valueKey="checkoutMean"
          opts={{ lowerIsBetter: true }}
        />
        <ChartCard
          title="p95 Checkout Latency"
          subtitle="Most important for production · green = best, red = worst"
          data={ALGORITHMS}
          valueKey="checkoutP95"
          opts={{ lowerIsBetter: true, markWorst: true }}
        />
      </div>

      {/* Summary table */}
      <div className="card" style={{ marginBottom: 16 }}>
        <h3 className="section-title">Full Metrics</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Algorithm</th>
                <th>Catalog mean</th>
                <th>Catalog p95</th>
                <th>Catalog max</th>
                <th>Checkout mean</th>
                <th>Checkout p95</th>
                <th>Wall time</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>
                  Single Worker <span className="muted">(baseline)</span>
                </td>
                <td>1969 ms</td>
                <td>2075 ms</td>
                <td>2188 ms</td>
                <td className="muted">N/A</td>
                <td className="muted">N/A</td>
                <td className="muted">25.38 req/s</td>
              </tr>
              {ALGORITHMS.map((a) => (
                <tr key={a.key}>
                  <td>
                    {a.name}
                    {a.active && (
                      <span
                        className="badge"
                        style={{
                          marginLeft: 8,
                          background: 'rgba(16,185,129,0.15)',
                          color: 'var(--success)',
                        }}
                      >
                        active
                      </span>
                    )}
                  </td>
                  <td>{fmt(a.catalogMean)} ms</td>
                  <td>{a.catalogP95 == null ? '—' : `${a.catalogP95} ms`}</td>
                  <td>{a.catalogMax == null ? '—' : `${a.catalogMax} ms`}</td>
                  <td>{fmt(a.checkoutMean)} ms</td>
                  <td>{fmt(a.checkoutP95)} ms</td>
                  <td>{a.wallTime}s</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Winner card */}
      <div
        className="card"
        style={{ marginBottom: 32, borderColor: 'rgba(99,102,241,0.4)' }}
      >
        <h3 className="section-title">
          <TrophyIcon width={18} height={18} style={{ color: 'var(--warning)' }} /> Winners by
          Scenario
        </h3>
        <div
          className="grid"
          style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))' }}
        >
          {WINNERS.map((w) => (
            <div
              key={w.tag}
              style={{
                background: w.win ? 'rgba(16,185,129,0.1)' : 'var(--bg-secondary)',
                border: `1px solid ${w.win ? 'var(--success)' : 'var(--border)'}`,
                borderRadius: 10,
                padding: 16,
              }}
            >
              <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
                Best for {w.tag}
              </div>
              <div style={{ fontWeight: 700, fontSize: 15 }}>
                {w.name}
                {w.win && <span style={{ color: 'var(--success)', marginLeft: 6 }}>✓</span>}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ---------- Section 3: Locked placeholders ---------- */}
      <h3 className="section-title">More Benchmarks</h3>
      <div
        className="grid"
        style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))' }}
      >
        {LOCKED.map((l) => (
          <div
            key={l.session}
            className="card"
            style={{ opacity: 0.6, position: 'relative' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <LockIcon width={16} height={16} className="muted" />
              <h4 style={{ fontSize: 14 }}>{l.session}</h4>
            </div>
            <p className="muted" style={{ fontSize: 13, marginBottom: 16, minHeight: 36 }}>
              {l.metric}
            </p>
            <button className="btn" disabled>
              Run Benchmark
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
