import { NavLink, useNavigate } from 'react-router-dom'
import { TOKEN_KEY } from '../services/api'
import {
  HomeIcon,
  BoxIcon,
  ListIcon,
  WarehouseIcon,
  UsersIcon,
  ShieldIcon,
  ChartIcon,
  LogoutIcon,
} from './icons'

const NAV = [
  { to: '/dashboard', label: 'Dashboard', Icon: HomeIcon },
  { to: '/products', label: 'Products', Icon: BoxIcon },
  { to: '/orders', label: 'Orders', Icon: ListIcon },
  { to: '/inventory', label: 'Inventory', Icon: WarehouseIcon },
  { to: '/customers', label: 'Customers', Icon: UsersIcon },
  { to: '/employees', label: 'Employees & Roles', Icon: ShieldIcon },
  { to: '/performance', label: 'Performance', Icon: ChartIcon },
]

export default function Sidebar() {
  const navigate = useNavigate()

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY)
    navigate('/login', { replace: true })
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <span className="logo-mark">◆</span>
        <span>Ordering Admin</span>
      </div>

      <nav>
        {NAV.map(({ to, label, Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
          >
            <Icon className="nav-icon" />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="nav-item" onClick={logout}>
          <LogoutIcon className="nav-icon" />
          <span>Logout</span>
        </div>
      </div>
    </aside>
  )
}
