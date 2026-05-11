import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useRequests } from '../hooks/useRequests'
import StatusBadge from '../components/requests/StatusBadge'
import { formatDateTime } from '../utils/formatters'
import { deleteRequest } from '../api/client'

export default function RequestListPage() {
  const [deletingId, setDeletingId] = useState(null)
  const { requests, total, isLoading, error, refetch } = useRequests()

  async function handleDelete(id, title) {
    if (!window.confirm(`Delete "${title}"? This cannot be undone.`)) return
    setDeletingId(id)
    try {
      await deleteRequest(id)
      refetch()
    } finally {
      setDeletingId(null)
    }
  }

  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '4rem' }}>
        <span className="spinner" style={{ width: 32, height: 32 }} />
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ textAlign: 'center', padding: '4rem', color: 'var(--danger)' }}>
        <p>Could not load requests: {error}</p>
        <button className="btn btn-outline mt-4" onClick={refetch}>Retry</button>
      </div>
    )
  }

  return (
    <div>
      <div className="flex justify-between items-center" style={{ marginBottom: '1.5rem' }}>
        <div>
          <h2 style={{ fontWeight: 800, fontSize: '1.5rem' }}>My Requests</h2>
          <p className="text-sm text-muted">{total} request{total !== 1 ? 's' : ''} total</p>
        </div>
        <Link to="/requests/new" className="btn btn-primary">+ New Request</Link>
      </div>

      {requests.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
          <p style={{ fontSize: '1.1rem', marginBottom: '1rem' }}>No requests yet.</p>
          <Link to="/requests/new" className="btn btn-primary">Create your first request</Link>
        </div>
      ) : (
        <div className="card" style={{ padding: 0 }}>
          <table style={{ width: '100%' }}>
            <thead>
              <tr>
                <th style={{ padding: '1rem' }}>Job Title</th>
                <th>Status</th>
                <th>Platforms</th>
                <th>Candidates</th>
                <th>Created</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {requests.map(r => (
                <tr key={r.id}>
                  <td style={{ fontWeight: 600, padding: '1rem' }}>
                    {r.title}
                  </td>
                  <td><StatusBadge status={r.status} /></td>
                  <td>
                    <div className="chips">
                      {r.platforms.map(p => (
                        <span key={p} className="chip">{p}</span>
                      ))}
                    </div>
                  </td>
                  <td>{r.candidate_count}</td>
                  <td className="text-sm text-muted">{formatDateTime(r.created_at)}</td>
                  <td style={{ display: 'flex', gap: '0.5rem', padding: '1rem' }}>
                    <Link to={`/requests/${r.id}`} className="btn btn-outline btn-sm">View</Link>
                    <button
                      className="btn btn-sm"
                      style={{ background: 'var(--danger)', color: '#fff', border: 'none' }}
                      disabled={deletingId === r.id}
                      onClick={() => handleDelete(r.id, r.title)}
                    >
                      {deletingId === r.id ? '...' : 'Delete'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
