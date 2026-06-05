import { useEffect, useState } from 'react'
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
import api from '../services/api'
import { LockIcon, TrophyIcon } from '../components/icons'

// ---------------------------------------------------------------------------
// Palette
// ---------------------------------------------------------------------------
const GREEN = '#1D9E75'
const RED = '#E24B4A'
const PURPLE = '#6366f1'
const GRID = 'rgba(128,128,128,0.15)'

// ---------------------------------------------------------------------------
// Small shared helpers
// ---------------------------------------------------------------------------
const fmt = (v, suffix = '') => (v == null ? '—' : `${v}${suffix}`)

// Color each bar: lowest green / highest red / rest purple (nulls ignored).
function tint(data, key, { lowerIsBetter = true } = {}) {
  const vals = data.map((d) => d[key]).filter((v) => v != null)
  if (!vals.length) return data.map((d) => ({ ...d, fill: PURPLE }))
  const min = Math.min(...vals)
  const max = Math.max(...vals)
  const best = lowerIsBetter ? min : max
  const worst = lowerIsBetter ? max : min
  return data.map((d) => {
    let fill = PURPLE
    if (d[key] === best) fill = GREEN
    else if (d[key] === worst) fill = RED
    return { ...d, fill }
  })
}

function CustomTooltip({ active, payload, label, unit }) {
  if (!active || !payload || !payload.length) return null
  return (
    <div
      style={{
        background: '#1a1d27',
        border: '1px solid #2d3148',
        borderRadius: 8,
        padding: '8px 12px',
        color: '#f1f5f9',
        fontSize: 13,
      }}
    >
      <div style={{ marginBottom: 4, fontWeight: 600 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: '#cbd5e1' }}>
          {p.value == null ? '—' : `${p.value}${unit || ''}`}
        </div>
      ))}
    </div>
  )
}

function BarCard({ title, subtitle, data, dataKey, xKey = 'name', unit = ' ms', lowerIsBetter = true }) {
  const rows = tint(
    data.filter((d) => d[dataKey] != null),
    dataKey,
    { lowerIsBetter },
  )
  return (
    <div className="card">
      <h4 style={{ fontSize: 14, marginBottom: 2 }}>{title}</h4>
      {subtitle && (
        <p className="muted" style={{ fontSize: 12, marginBottom: 12 }}>
          {subtitle}
        </p>
      )}
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={rows} margin={{ top: 8, right: 8, left: -10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
          <XAxis dataKey={xKey} tick={{ fill: '#cbd5e1', fontSize: 11 }} />
          <YAxis tick={{ fill: '#cbd5e1', fontSize: 11 }} />
          <Tooltip content={<CustomTooltip unit={unit} />} cursor={{ fill: 'rgba(99,102,241,0.08)' }} />
          <Bar dataKey={dataKey} radius={[6, 6, 0, 0]}>
            {rows.map((entry, i) => (
              <Cell key={i} fill={entry.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function Section({ title, action, children }) {
  return (
    <div style={{ marginBottom: 48 }}>
      <div
        style={{
          borderLeft: '4px solid var(--accent)',
          paddingLeft: 12,
          marginBottom: 24,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <h2 style={{ fontSize: 18 }}>{title}</h2>
        {action}
      </div>
      {children}
    </div>
  )
}

function RunButton({ session, running, onRun }) {
  const isRunning = !!running[session]
  return (
    <button className="btn" disabled={isRunning} onClick={() => onRun(session)}>
      {isRunning ? (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
          <span
            className="spinner"
            style={{ width: 14, height: 14, borderWidth: 2, display: 'inline-block' }}
          />
          Running…
        </span>
      ) : (
        'Run Benchmark'
      )}
    </button>
  )
}

function NoData({ canRun }) {
  return (
    <div className="card" style={{ textAlign: 'center', padding: 36 }}>
      <p className="muted" style={{ margin: 0 }}>
        {canRun
          ? 'No data yet — click Run Benchmark to generate results'
          : 'No data yet'}
      </p>
    </div>
  )
}

function badge(text, color) {
  return (
    <span
      className="badge"
      style={{ background: `${color}26`, color, marginLeft: 8 }}
    >
      {text}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function Performance() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [running, setRunning] = useState({})

  const fetchData = async () => {
    try {
      const res = await api.get('/api/v1/admin/performance-data/')
      setData(res.data)
      setError(null)
    } catch (e) {
      setError('Failed to load performance data')
    } finally {
      setLoading(false)
    }
  }

  const runBenchmark = async (session) => {
    setRunning((prev) => ({ ...prev, [session]: true }))
    try {
      await api.post(`/api/v1/admin/run-benchmark/${session}/`)
      const poll = setInterval(async () => {
        try {
          const res = await api.get(`/api/v1/admin/benchmark-status/${session}/`)
          if (!res.data.running) {
            clearInterval(poll)
            setRunning((prev) => ({ ...prev, [session]: false }))
            fetchData()
          }
        } catch (e) {
          clearInterval(poll)
          setRunning((prev) => ({ ...prev, [session]: false }))
        }
      }, 1500)
    } catch (e) {
      setRunning((prev) => ({ ...prev, [session]: false }))
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  if (loading) {
    return (
      <div className="page">
        <div className="center-screen">
          <div className="spinner" />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="page">
        <div className="empty-state">
          <div className="big-icon">⚠️</div>
          <p>{error}</p>
          <button className="btn" onClick={fetchData} style={{ marginTop: 12 }}>
            Retry
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Performance Dashboard</h1>
          <p className="page-subtitle">Live benchmark results — Parallel Programming Course</p>
        </div>
      </div>

      <SetupSection />
      <LoadBalancingSection data={data?.algorithms} />
      <RaceConditionSection data={data?.checkout_race} running={running} onRun={runBenchmark} />
      <ThreadPoolSection data={data?.thread_pool} running={running} onRun={runBenchmark} />
      <BatchEtlSection data={data?.batch_etl} running={running} onRun={runBenchmark} />
      <CacheSection data={data?.cache} />
      <ConcurrencySection data={data?.concurrency} running={running} onRun={runBenchmark} />
      <MessageQueueSection />
      <TestingSummarySection data={data?.testing_summary} />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Section 1 — System Configuration
// ---------------------------------------------------------------------------
const SETUP = [
  { label: 'Load Balancer', value: 'Nginx 1.30.1' },
  { label: 'Workers', value: '3 × Waitress (threads=4)' },
  { label: 'Algorithm', value: 'Least Connections', active: true },
  { label: 'Database', value: 'PostgreSQL 18' },
]

function SetupSection() {
  return (
    <Section title="System Configuration">
      <div
        className="grid"
        style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}
      >
        {SETUP.map((s) => (
          <div className="stat-card" key={s.label}>
            <div className="stat-label">{s.label}</div>
            <div style={{ fontSize: 18, fontWeight: 700, marginTop: 8 }}>
              {s.value}
              {s.active && badge('✅ Active', 'var(--success)')}
            </div>
          </div>
        ))}
      </div>
    </Section>
  )
}

// ---------------------------------------------------------------------------
// Section 2 — Session 5: Load Balancing
// ---------------------------------------------------------------------------
function LoadBalancingSection({ data }) {
  if (!data || !data.algorithms) {
    return (
      <Section title="Session 5 — Load Balancing">
        <NoData canRun={false} />
      </Section>
    )
  }

  const algos = data.algorithms
  const catalog = algos.map((a) => ({ name: a.name, value: a.catalog_mean }))
  const checkout = algos
    .filter((a) => a.checkout_mean != null)
    .map((a) => ({ name: a.name, value: a.checkout_mean }))
  const p95 = algos
    .filter((a) => a.checkout_p95 != null)
    .map((a) => ({ name: a.name, value: a.checkout_p95 }))

  const minBy = (key) => {
    const valid = algos.filter((a) => a[key] != null)
    return valid.length ? valid.reduce((m, a) => (a[key] < m[key] ? a : m)) : null
  }
  const maxBy = (key) => {
    const valid = algos.filter((a) => a[key] != null)
    return valid.length ? valid.reduce((m, a) => (a[key] > m[key] ? a : m)) : null
  }

  const winners = [
    { tag: 'Mixed Workload', name: algos.find((a) => a.is_active)?.name || '—', win: true },
    { tag: 'Best p95', name: minBy('checkout_p95')?.name || '—' },
    { tag: 'Best Req/sec', name: maxBy('req_per_sec')?.name || '—' },
    { tag: 'Best Checkout', name: minBy('checkout_mean')?.name || '—' },
  ]

  return (
    <Section title="Session 5 — Load Balancing">
      <p className="muted" style={{ fontSize: 12, marginBottom: 14 }}>
        Last updated: {data.last_updated?.slice(0, 10) || '—'}
      </p>

      <div
        className="grid"
        style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', marginBottom: 16 }}
      >
        <BarCard title="Catalog Mean Latency" subtitle="Lower is better" data={catalog} dataKey="value" />
        <BarCard title="Checkout Mean Latency" subtitle="Lower is better" data={checkout} dataKey="value" />
        <BarCard title="p95 Checkout Latency" subtitle="Most important for production" data={p95} dataKey="value" />
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Algorithm</th>
                <th>Catalog Mean</th>
                <th>Catalog p95</th>
                <th>Checkout Mean</th>
                <th>Checkout p95</th>
                <th>Req/sec</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {algos.map((a) => (
                <tr key={a.name}>
                  <td>{a.name}</td>
                  <td>{fmt(a.catalog_mean, ' ms')}</td>
                  <td>{fmt(a.catalog_p95, ' ms')}</td>
                  <td>{fmt(a.checkout_mean, ' ms')}</td>
                  <td>{fmt(a.checkout_p95, ' ms')}</td>
                  <td>{fmt(a.req_per_sec)}</td>
                  <td>{a.is_active ? badge('Active', 'var(--success)') : a.label || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <h4 className="section-title">
          <TrophyIcon width={18} height={18} style={{ color: 'var(--warning)' }} /> Winners by Scenario
        </h4>
        <div className="grid" style={{ gridTemplateColumns: 'repeat(2, 1fr)' }}>
          {winners.map((w) => (
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
                {w.tag}
              </div>
              <div style={{ fontWeight: 700 }}>{w.name}</div>
            </div>
          ))}
        </div>
      </div>
    </Section>
  )
}

// ---------------------------------------------------------------------------
// Section 3 — Session 2: Thread Pool
// ---------------------------------------------------------------------------
function ThreadPoolSection({ data, running, onRun }) {
  const action = <RunButton session="thread_pool" running={running} onRun={onRun} />
  if (!data || !data.strategies) {
    return (
      <Section title="Session 2 — Thread Pool Management" action={action}>
        <NoData canRun />
      </Section>
    )
  }

  const sc = data.scenario || {}
  const durData = data.strategies.map((s) => ({ name: s.name, value: s.duration_ms }))
  const okData = data.strategies.map((s) => ({ name: s.name, value: s.successful_orders }))

  return (
    <Section title="Session 2 — Thread Pool Management" action={action}>
      <p className="muted" style={{ fontSize: 13, marginBottom: 16 }}>
        {sc.pending_orders ?? 40} orders | External service capacity: {sc.external_service_capacity ?? 8} | Call time:{' '}
        {sc.external_call_ms ?? 200}ms
      </p>

      <div
        className="grid"
        style={{ gridTemplateColumns: 'repeat(2, 1fr)', marginBottom: 16 }}
      >
        {data.strategies.map((s) => (
          <div
            key={s.name}
            className="card"
            style={s.recommended ? { borderColor: 'var(--success)' } : undefined}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <strong>{s.name}</strong>
              <code style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{s.label}</code>
              {s.recommended && badge('🏆 Winner', 'var(--success)')}
            </div>
            <div style={{ display: 'grid', gap: 4, fontSize: 13 }}>
              <div>✅ Successful: {s.successful_orders} / ❌ Failed: {s.failed_orders}</div>
              <div>⚡ Throughput: {s.throughput_orders_per_sec} ord/sec</div>
              <div>⏱ Duration: {Math.round(s.duration_ms)}ms</div>
              <div>⚠️ Overload events: {s.overload_events}</div>
              <div>🧵 Threads created: {s.created_threads}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid" style={{ gridTemplateColumns: 'repeat(2, 1fr)', marginBottom: 16 }}>
        <BarCard title="Duration (ms)" subtitle="Lower is better" data={durData} dataKey="value" />
        <BarCard
          title="Successful Orders"
          subtitle="Higher is better"
          data={okData}
          dataKey="value"
          unit=""
          lowerIsBetter={false}
        />
      </div>

      {data.lesson && (
        <div
          className="card"
          style={{ background: 'rgba(99,102,241,0.1)', borderColor: 'var(--accent)' }}
        >
          💡 <strong>Lesson:</strong> {data.lesson}
        </div>
      )}
    </Section>
  )
}

// ---------------------------------------------------------------------------
// Section 4 — Session 4: Batch ETL
// ---------------------------------------------------------------------------
function BatchEtlSection({ data, running, onRun }) {
  const action = <RunButton session="batch_etl" running={running} onRun={onRun} />
  if (!data || !data.realtime || !data.batch) {
    return (
      <Section title="Session 4 — Batch Processing" action={action}>
        <NoData canRun />
      </Section>
    )
  }

  const chart = [
    { name: 'Real-Time', value: Math.round(data.realtime.processing_time_ms) },
    { name: 'Batch ETL', value: Math.round(data.batch.processing_time_ms) },
  ]

  return (
    <Section title="Session 4 — Batch Processing" action={action}>
      <div className="grid" style={{ gridTemplateColumns: 'repeat(2, 1fr)', marginBottom: 16 }}>
        <div className="card" style={{ borderColor: 'var(--danger)' }}>
          <div className="muted" style={{ fontSize: 12 }}>❌ Problem</div>
          <h4 style={{ marginTop: 6 }}>{data.realtime.label}</h4>
          <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--danger)', marginTop: 8 }}>
            {Math.round(data.realtime.processing_time_ms)} ms
          </div>
        </div>
        <div className="card" style={{ borderColor: 'var(--success)' }}>
          <div className="muted" style={{ fontSize: 12 }}>✅ Solution</div>
          <h4 style={{ marginTop: 6 }}>{data.batch.label}</h4>
          <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--success)', marginTop: 8 }}>
            {Math.round(data.batch.processing_time_ms)} ms
          </div>
        </div>
      </div>

      <div style={{ textAlign: 'center', margin: '24px 0' }}>
        <span style={{ fontSize: 40, fontWeight: 800, color: 'var(--accent)' }}>
          {data.comparison?.speedup}x faster
        </span>
      </div>

      <div style={{ marginBottom: 16 }}>
        <BarCard title="Processing Time" subtitle="Real-Time vs Batch" data={chart} dataKey="value" />
      </div>

      <div className="card">
        <div className="grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
          <Detail k="Total Orders" v={data.total_orders} />
          <Detail k="Chunks" v={`${data.batch.chunks_successful} ok / ${data.batch.chunks_failed} fail`} />
          <Detail k="Time Saved" v={`${Math.round(data.comparison?.time_saved_ms)} ms`} />
          <Detail k="Inventory Match" v={data.comparison?.inventory_match ? '✓' : '✗'} />
        </div>
      </div>
    </Section>
  )
}

function Detail({ k, v }) {
  return (
    <div>
      <div className="muted" style={{ fontSize: 12 }}>{k}</div>
      <div style={{ fontWeight: 700, marginTop: 4 }}>{v}</div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Section 5 — Session 6: Redis Caching
// ---------------------------------------------------------------------------
function CacheSection({ data }) {
  if (!data) {
    return (
      <Section title="Session 6 — Redis Caching">
        <NoData canRun={false} />
      </Section>
    )
  }

  const rate = data.hit_rate_percent ?? 0
  const rateColor = rate > 80 ? 'var(--success)' : rate >= 50 ? 'var(--warning)' : 'var(--danger)'
  const chart = [
    { name: 'Database', value: Math.round(data.last_db_latency_ms || 0) },
    { name: 'Redis Cache', value: Math.round(data.avg_cache_latency_ms || 0) },
  ]

  return (
    <Section title="Session 6 — Redis Caching">
      <p className="muted" style={{ fontSize: 12, marginBottom: 16 }}>
        Auto-updates on every catalog API request
      </p>

      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
          <strong>Cache Hit Rate</strong>
          <strong style={{ color: rateColor }}>{rate}%</strong>
        </div>
        <div style={{ height: 14, borderRadius: 8, background: 'var(--bg-secondary)', overflow: 'hidden' }}>
          <div style={{ width: `${rate}%`, height: '100%', background: rateColor, transition: 'width .4s' }} />
        </div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: 'repeat(2, 1fr)', marginBottom: 16 }}>
        <div className="card">
          <div className="muted" style={{ fontSize: 12 }}>Database · Cache Miss</div>
          <div style={{ fontSize: 26, fontWeight: 700, color: 'var(--danger)', marginTop: 8 }}>
            {Math.round(data.last_db_latency_ms || 0)} ms
          </div>
        </div>
        <div className="card">
          <div className="muted" style={{ fontSize: 12 }}>Redis Cache · Cache Hit</div>
          <div style={{ fontSize: 26, fontWeight: 700, color: 'var(--success)', marginTop: 8 }}>
            {data.avg_cache_latency_ms || 0} ms
          </div>
        </div>
      </div>

      <div style={{ textAlign: 'center', margin: '20px 0' }}>
        <span style={{ fontSize: 34, fontWeight: 800, color: 'var(--accent)' }}>
          {data.speedup}x faster with Redis
        </span>
      </div>

      <div style={{ marginBottom: 16 }}>
        <BarCard title="Latency" subtitle="DB vs Cache" data={chart} dataKey="value" />
      </div>

      <div className="card">
        <div className="grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
          <Detail k="Pattern" v={data.pattern} />
          <Detail k="Lock" v={data.lock_mechanism} />
          <Detail k="TTL" v="900s" />
          <Detail k="Total Requests" v={data.total_requests} />
        </div>
      </div>
    </Section>
  )
}

// ---------------------------------------------------------------------------
// Section 6 — Session 7: Concurrency Control
// ---------------------------------------------------------------------------
function ConcurrencySection({ data, running, onRun }) {
  const action = <RunButton session="concurrency" running={running} onRun={onRun} />
  if (!data || !data.strategies) {
    return (
      <Section title="Session 7 — Concurrency Control" action={action}>
        <NoData canRun />
      </Section>
    )
  }

  const chart = data.strategies.map((s) => ({
    name: s.name.replace(' Locking', '').replace(' Expression', ''),
    value: s.throughput_orders_per_sec,
  }))

  return (
    <Section title="Session 7 — Concurrency Control" action={action}>
      <p className="muted" style={{ fontSize: 13, marginBottom: 16 }}>
        {data.num_users || 100} concurrent users | Stock: {data.stock_per_run || 50} units | Zero data corruption
      </p>

      <div className="grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)', marginBottom: 16 }}>
        {data.strategies.map((s) => {
          const isWinner = s.name === data.winner
          return (
            <div
              key={s.name}
              className="card"
              style={isWinner ? { borderColor: 'var(--warning)' } : undefined}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <strong>{s.name}</strong>
                {isWinner && badge('🏆 Winner', 'var(--warning)')}
              </div>
              <code style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{s.method}</code>
              <div style={{ display: 'grid', gap: 4, fontSize: 13, marginTop: 10 }}>
                <div>✅ Successful: {s.successful_orders} | ❌ Failed: {s.failed_orders}</div>
                <div>⚡ Throughput: {s.throughput_orders_per_sec} ord/sec</div>
                <div>⏱ Avg Latency: {s.avg_latency_ms}ms</div>
                <div>
                  🔒 Data Integrity:{' '}
                  <span style={{ color: s.data_integrity ? 'var(--success)' : 'var(--danger)' }}>
                    {s.data_integrity ? '✓' : '✗'}
                  </span>
                </div>
              </div>
            </div>
          )
        })}
      </div>

      <div style={{ marginBottom: 16 }}>
        <BarCard
          title="Throughput (ord/sec)"
          subtitle="Higher is better"
          data={chart}
          dataKey="value"
          unit=" ord/sec"
          lowerIsBetter={false}
        />
      </div>

      {data.integrity_verified && (
        <div
          className="card"
          style={{ background: 'rgba(16,185,129,0.1)', borderColor: 'var(--success)' }}
        >
          🔒 Data integrity verified across all strategies
        </div>
      )}
    </Section>
  )
}

// ---------------------------------------------------------------------------
// Section 7 — Session 3: Message Queue (locked)
// ---------------------------------------------------------------------------
function MessageQueueSection() {
  return (
    <Section title="Session 3 — Async Message Queue">
      <div className="card" style={{ background: 'var(--bg-secondary)', opacity: 0.75 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
          <LockIcon width={16} height={16} className="muted" />
          <strong>Requires RabbitMQ + Celery worker</strong>
        </div>
        <p className="muted" style={{ fontSize: 13, margin: 0 }}>
          Run: <code>python manage.py simulate_async_queue</code>
        </p>
      </div>
    </Section>
  )
}

// ---------------------------------------------------------------------------
// Session 1 — Race Conditions (data-driven, placed before Session 2)
// ---------------------------------------------------------------------------
function RaceConditionSection({ data, running, onRun }) {
  const action = <RunButton session="checkout_race" running={running} onRun={onRun} />
  if (!data || !data.strategies) {
    return (
      <Section title="Session 1 — Race Conditions" action={action}>
        <NoData canRun />
      </Section>
    )
  }

  const shortName = {
    'Unsafe Read-Then-Write': 'Unsafe',
    'Row Lock': 'Row Lock',
    'Atomic Conditional Update': 'Atomic',
  }
  const chart = data.strategies.map((s) => ({
    name: shortName[s.name] || s.name,
    value: Math.round(s.duration_ms),
  }))

  return (
    <Section title="Session 1 — Race Conditions" action={action}>
      <p className="muted" style={{ fontSize: 13, marginBottom: 16 }}>
        1 unit stock | 2 parallel checkouts | Who wins the race?
      </p>

      <div className="grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)', marginBottom: 16 }}>
        {data.strategies.map((s) => {
          const isWinner = s.name === data.winner
          return (
            <div
              key={s.name}
              className="card"
              style={{ borderColor: s.safe ? 'var(--success)' : 'var(--danger)' }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <strong>{s.name}</strong>
                {isWinner && badge('🏆 Winner', 'var(--warning)')}
              </div>
              <code style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{s.method}</code>
              <div style={{ marginTop: 10 }}>
                {s.safe ? badge('SAFE ✅', 'var(--success)') : badge('OVERSOLD ❌', 'var(--danger)')}
              </div>
              <div style={{ display: 'grid', gap: 4, fontSize: 13, marginTop: 10 }}>
                <div>Successes: {s.successes} | Failures: {s.failures}</div>
                <div>
                  Oversold units:{' '}
                  <span style={{ color: s.oversold_units > 0 ? 'var(--danger)' : 'var(--success)' }}>
                    {s.oversold_units}
                  </span>
                </div>
                <div>Duration: {Math.round(s.duration_ms)}ms</div>
              </div>
            </div>
          )
        })}
      </div>

      <div style={{ marginBottom: 16 }}>
        <BarCard title="Duration (ms)" subtitle="Lower is better" data={chart} dataKey="value" />
      </div>

      <div className="card" style={{ background: 'rgba(99,102,241,0.1)', borderColor: 'var(--accent)' }}>
        <div style={{ display: 'grid', gap: 6, fontSize: 13 }}>
          <div>❌ Unsafe: 1 stock → 2 orders (OVERSOLD)</div>
          <div>✅ Row Lock: 1 stock → 1 order (safe but slower)</div>
          <div>✅ Atomic: 1 stock → 1 order (fastest + safe)</div>
        </div>
      </div>
    </Section>
  )
}

// ---------------------------------------------------------------------------
// Session 8 — Testing & Benchmarking Summary (static, placed last)
// ---------------------------------------------------------------------------
function TestingSummarySection({ data }) {
  if (!data || !data.benchmarks) {
    return (
      <Section title="Session 8 — Testing & Benchmarking">
        <NoData canRun={false} />
      </Section>
    )
  }

  return (
    <Section title="Session 8 — Testing & Benchmarking">
      <div
        className="grid"
        style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', marginBottom: 16 }}
      >
        {data.benchmarks.map((b) => (
          <div className="card" key={`${b.session}-${b.name}`}>
            <div style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 600 }}>{b.session}</div>
            <h4 style={{ margin: '6px 0' }}>{b.name}</h4>
            <div className="muted" style={{ fontSize: 12 }}>{b.tool}</div>
            <div className="muted" style={{ fontSize: 12, marginBottom: 10 }}>{b.config}</div>
            <div style={{ fontSize: 22, fontWeight: 800, color: 'var(--accent)' }}>{b.key_metric}</div>
            <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>{b.best_result}</div>
          </div>
        ))}
      </div>

      <div className="card">
        <h4 className="section-title">Key Lessons</h4>
        <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'grid', gap: 8 }}>
          {data.key_lessons.map((lesson, i) => (
            <li key={i} style={{ fontSize: 13 }}>
              <span style={{ color: 'var(--success)', marginRight: 8 }}>✓</span>
              {lesson}
            </li>
          ))}
        </ul>
      </div>
    </Section>
  )
}
