import { lazy, Suspense } from 'react'
import { BrowserRouter, Link, Navigate, Outlet, Route, Routes, useLocation } from 'react-router'
import { Layout } from './components/Layout'
import { Empty, Spinner } from './components/ui'
import { useAuth } from './lib/auth'
import { AckPage } from './pages/AckPage'
import { DashboardPage } from './pages/Dashboard'
import { ForgotPasswordPage, LoginPage, ResetPasswordPage } from './pages/public'

// Secondary pages are split out of the main bundle (ApexCharts in particular).
const FridgeDetailPage = lazy(() =>
  import('./pages/FridgeDetail').then((m) => ({ default: m.FridgeDetailPage })),
)
const HistoryPage = lazy(() => import('./pages/History').then((m) => ({ default: m.HistoryPage })))
const IncidentsPage = lazy(() => import('./pages/Incidents').then((m) => ({ default: m.IncidentsPage })))
const IncidentDetailPage = lazy(() =>
  import('./pages/IncidentDetail').then((m) => ({ default: m.IncidentDetailPage })),
)
const ProfilePage = lazy(() => import('./pages/Profile').then((m) => ({ default: m.ProfilePage })))
const AdminFridgesPage = lazy(() =>
  import('./pages/admin/Fridges').then((m) => ({ default: m.AdminFridgesPage })),
)
const AdminDevicesPage = lazy(() =>
  import('./pages/admin/Devices').then((m) => ({ default: m.AdminDevicesPage })),
)
const AdminUsersPage = lazy(() => import('./pages/admin/Users').then((m) => ({ default: m.AdminUsersPage })))
const AdminEventsPage = lazy(() =>
  import('./pages/admin/Events').then((m) => ({ default: m.AdminEventsPage })),
)

function RequireAuth() {
  const { status } = useAuth()
  const location = useLocation()
  if (status === 'loading') return <Spinner label="Ouverture de la session…" />
  if (status === 'anonymous') {
    return <Navigate to="/connexion" replace state={{ from: location.pathname + location.search }} />
  }
  return <Outlet />
}

function RequireAdmin() {
  const { user } = useAuth()
  if (!user?.is_admin) {
    return (
      <div className="card">
        <Empty title="Accès réservé à l’administrateur" />
      </div>
    )
  }
  return <Outlet />
}

function NotFound() {
  return (
    <div className="card">
      <Empty title="Page introuvable">
        <Link to="/">Retour au tableau de bord</Link>
      </Empty>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<Spinner />}>
        <Routes>
          <Route path="/connexion" element={<LoginPage />} />
          <Route path="/mot-de-passe-oublie" element={<ForgotPasswordPage />} />
          <Route path="/reinitialiser-mot-de-passe" element={<ResetPasswordPage />} />
          <Route path="/ack/:token" element={<AckPage />} />

          <Route element={<RequireAuth />}>
            <Route element={<Layout />}>
              <Route index element={<DashboardPage />} />
              <Route path="frigos/:id" element={<FridgeDetailPage />} />
              <Route path="historique" element={<HistoryPage />} />
              <Route path="incidents" element={<IncidentsPage />} />
              <Route path="incidents/:id" element={<IncidentDetailPage />} />
              <Route path="profil" element={<ProfilePage />} />
              <Route path="admin" element={<RequireAdmin />}>
                <Route path="frigos" element={<AdminFridgesPage />} />
                <Route path="noeuds" element={<AdminDevicesPage />} />
                <Route path="utilisateurs" element={<AdminUsersPage />} />
                <Route path="journal" element={<AdminEventsPage />} />
              </Route>
              <Route path="*" element={<NotFound />} />
            </Route>
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}
