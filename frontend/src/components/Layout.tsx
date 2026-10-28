import { useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router'
import useSWR from 'swr'
import { useAuth } from '../lib/auth'
import { fullName } from '../lib/format'
import { ROLE } from '../lib/labels'
import type { Page, Incident } from '../lib/types'
import {
  AlertIcon,
  BrandMark,
  ChipIcon,
  CloseIcon,
  DashboardIcon,
  FridgeIcon,
  HistoryIcon,
  LogIcon,
  MenuIcon,
  UsersIcon,
} from './icons'

function Brand() {
  return (
    <Link to="/" className="brand">
      <BrandMark className="brand-mark" />
      <span className="brand-name">
        Cold Chain
        <small>Monitoring · 2–8 °C</small>
      </span>
    </Link>
  )
}

export function Layout() {
  const { user, logout } = useAuth()
  const location = useLocation()
  const [menuFor, setMenuFor] = useState<string | null>(null)
  // The mobile menu closes itself on navigation: it is open only for the path it was opened on.
  const menuOpen = menuFor === location.pathname

  const { data: active } = useSWR<Page<Incident>>('/api/incidents/?active=true&page_size=1', {
    refreshInterval: 30_000,
  })

  if (!user) return null

  return (
    <div className="shell">
      <header className="topbar">
        <Brand />
        <button
          type="button"
          onClick={() => setMenuFor(menuOpen ? null : location.pathname)}
          aria-expanded={menuOpen}
          aria-label={menuOpen ? 'Fermer le menu' : 'Ouvrir le menu'}
        >
          {menuOpen ? <CloseIcon width={20} /> : <MenuIcon width={20} />}
        </button>
      </header>

      <aside className={`sidebar${menuOpen ? ' open' : ''}`}>
        <Brand />
        <nav className="nav" aria-label="Surveillance">
          <p className="nav-title">Surveillance</p>
          <NavLink to="/" end>
            <DashboardIcon /> Tableau de bord
          </NavLink>
          <NavLink to="/incidents">
            <AlertIcon /> Incidents
            {active?.count ? <span className="nav-count">{active.count}</span> : null}
          </NavLink>
          <NavLink to="/historique">
            <HistoryIcon /> Historique
          </NavLink>
        </nav>
        {user.is_admin ? (
          <nav className="nav" aria-label="Administration">
            <p className="nav-title">Administration</p>
            <NavLink to="/admin/frigos">
              <FridgeIcon /> Frigos
            </NavLink>
            <NavLink to="/admin/noeuds">
              <ChipIcon /> Nœuds IoT
            </NavLink>
            <NavLink to="/admin/utilisateurs">
              <UsersIcon /> Utilisateurs
            </NavLink>
            <NavLink to="/admin/journal">
              <LogIcon /> Journal
            </NavLink>
          </nav>
        ) : null}
        <div className="sidebar-footer">
          <strong>{fullName(user)}</strong>
          {ROLE[user.role]}
          <div className="links">
            <Link to="/profil">Mon profil</Link>
            <button type="button" onClick={() => void logout()}>
              Déconnexion
            </button>
          </div>
        </div>
      </aside>

      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}
