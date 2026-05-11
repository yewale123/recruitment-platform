import { Link, useLocation } from 'react-router-dom'
import './Navbar.css'

export default function Navbar() {
  const { pathname } = useLocation()

  return (
    <nav className="navbar">
      <div className="navbar-inner">
        <Link to="/" className="navbar-brand">RecruitAI</Link>
        <div className="navbar-links">
          <Link to="/requests" className={pathname.startsWith('/requests') && pathname !== '/requests/new' ? 'active' : ''}>
            My Requests
          </Link>
          <Link to="/requests/new" className={pathname === '/requests/new' ? 'active' : ''}>
            + New Request
          </Link>
        </div>
      </div>
    </nav>
  )
}
