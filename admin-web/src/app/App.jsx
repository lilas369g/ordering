export default function App() {
  const cards = [
    'Products & Variants',
    'Orders',
    'Inventory',
    'Customers',
    'Employees & Roles',
    'Reports',
  ]

  return (
    <main style={{fontFamily: 'sans-serif', padding: 24}}>
      <h1>Admin Dashboard Starter</h1>
      <p>React starter connected later to /api/v1/admin/* endpoints.</p>
      <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16, marginTop: 24}}>
        {cards.map((card) => (
          <section key={card} style={{border: '1px solid #ddd', borderRadius: 12, padding: 16}}>
            <h3>{card}</h3>
            <p>Feature module placeholder.</p>
          </section>
        ))}
      </div>
    </main>
  )
}
