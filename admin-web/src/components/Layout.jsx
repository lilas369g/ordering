import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'

// Shell shared by all protected pages: persistent sidebar + routed content.
export default function Layout() {
  return (
    <div className="app-shell">
      <Sidebar />
      <div className="main-area">
        <Outlet />
      </div>
    </div>
  )
}
