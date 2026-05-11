import { Routes, Route, Navigate } from 'react-router-dom'
import Navbar from './components/layout/Navbar'
import HomePage from './pages/HomePage'
import NewRequestPage from './pages/NewRequestPage'
import RequestListPage from './pages/RequestListPage'
import RequestDetailPage from './pages/RequestDetailPage'

export default function App() {
  return (
    <div className="app">
      <Navbar />
      <main className="main-content">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/requests/new" element={<NewRequestPage />} />
          <Route path="/requests" element={<RequestListPage />} />
          <Route path="/requests/:id" element={<RequestDetailPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}
