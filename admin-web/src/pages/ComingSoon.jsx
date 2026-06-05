// Reusable "Coming Soon" placeholder for not-yet-built modules.
export default function ComingSoon({ title, message, emoji = '🚧' }) {
  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">{title}</h1>
      </div>
      <div className="card">
        <div className="empty-state">
          <div className="big-icon">{emoji}</div>
          <h3 style={{ marginBottom: 8 }}>{message}</h3>
          <p className="muted">This module is on the roadmap.</p>
        </div>
      </div>
    </div>
  )
}
