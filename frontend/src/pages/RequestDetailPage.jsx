import { useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useRequest } from '../hooks/useRequest'
import StatusBadge from '../components/requests/StatusBadge'
import CandidateTable from '../components/candidates/CandidateTable'
import { formatDateTime } from '../utils/formatters'
import { deleteRequest } from '../api/client'

export default function RequestDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [deleting, setDeleting] = useState(false)
  const { request, candidates, isLoading, isPolling, error } = useRequest(Number(id))

  async function handleDelete() {
    if (!window.confirm(`Delete "${request.title}"? This cannot be undone.`)) return
    setDeleting(true)
    try {
      await deleteRequest(Number(id))
      navigate('/requests')
    } finally {
      setDeleting(false)
    }
  }

  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '4rem' }}>
        <span className="spinner" style={{ width: 32, height: 32 }} />
      </div>
    )
  }

  if (error || !request) {
    return (
      <div style={{ textAlign: 'center', padding: '4rem', color: 'var(--danger)' }}>
        <p>{error || 'Request not found'}</p>
        <Link to="/requests" className="btn btn-outline mt-4">Back to Requests</Link>
      </div>
    )
  }

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: '1.5rem' }}>
        <Link to="/requests" style={{ fontSize: '.875rem', color: 'var(--gray-600)' }}>← All Requests</Link>
        <div className="flex justify-between items-center mt-2">
          <h2 style={{ fontWeight: 800, fontSize: '1.5rem' }}>{request.title}</h2>
          <div className="flex items-center gap-2">
            <StatusBadge status={request.status} />
            <button
              className="btn btn-sm"
              style={{ background: 'var(--danger)', color: '#fff', border: 'none' }}
              disabled={deleting}
              onClick={handleDelete}
            >
              {deleting ? 'Deleting…' : 'Delete'}
            </button>
          </div>
        </div>
        <p className="text-sm text-muted">Created {formatDateTime(request.created_at)}</p>
      </div>

      {/* Request meta */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem' }}>
          <div>
            <p className="text-sm text-muted">Required Skills</p>
            <div className="chips mt-1">
              {request.required_skills.map(s => (
                <span key={s} className="chip matched">{s}</span>
              ))}
            </div>
          </div>
          <div>
            <p className="text-sm text-muted">Experience</p>
            <p style={{ fontWeight: 600 }}>
              {request.experience_min}
              {request.experience_max ? `–${request.experience_max}` : '+'} years
            </p>
          </div>
          <div>
            <p className="text-sm text-muted">Location</p>
            <p style={{ fontWeight: 600 }}>{request.location || 'Any'}</p>
          </div>
          <div>
            <p className="text-sm text-muted">Platforms</p>
            <div className="chips mt-1">
              {request.platforms.map(p => (
                <span key={p} className="chip">{p}</span>
              ))}
            </div>
          </div>
          {request.keywords?.length > 0 && (
            <div>
              <p className="text-sm text-muted">Keywords</p>
              <div className="chips mt-1">
                {request.keywords.map(k => <span key={k} className="chip">{k}</span>)}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Progress while running */}
      {(request.status === 'pending' || request.status === 'running') && (
        <div className="progress-section" style={{ marginBottom: '1.5rem' }}>
          <div className="flex items-center gap-2">
            <span className="spinner" />
            <strong>Searching for candidates…</strong>
            {isPolling && <span className="text-sm text-muted">(auto-refreshing every 5s)</span>}
          </div>
          {request.scrape_jobs?.map(job => (
            <div key={job.id} style={{ marginTop: '0.75rem' }}>
              <div className="progress-row">
                <span style={{ textTransform: 'capitalize', fontWeight: 600, width: 80 }}>{job.platform}</span>
                <StatusBadge status={job.status} />
                {job.candidates_found > 0 && (
                  <span className="text-sm text-muted">{job.candidates_found} found</span>
                )}
              </div>
              {job.status === 'failed' && job.error_message && (
                <p className="text-sm" style={{ color: 'var(--danger)', marginTop: '0.25rem', marginLeft: 88, wordBreak: 'break-all' }}>
                  {job.error_message.split('\n')[0]}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Failed */}
      {request.status === 'failed' && (
        <div style={{ padding: '1.5rem', background: '#fee2e2', borderRadius: 'var(--radius)', marginBottom: '1.5rem', color: 'var(--danger)' }}>
          <strong>Scraping failed.</strong>
          {request.scrape_jobs?.filter(j => j.status === 'failed').map(j => (
            <div key={j.id} className="mt-1">
              <p className="text-sm" style={{ fontWeight: 600, textTransform: 'capitalize' }}>{j.platform}</p>
              <p className="text-sm" style={{ wordBreak: 'break-all' }}>{j.error_message?.split('\n')[0] || 'Unknown error'}</p>
            </div>
          ))}
        </div>
      )}

      {/* Results */}
      {request.status === 'completed' && (
        <div className="card" style={{ padding: 0 }}>
          <div style={{ padding: '1rem 1.5rem', borderBottom: '1.5px solid var(--gray-100)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ fontWeight: 700 }}>Ranked Candidates</h3>
            <span className="text-sm text-muted">{candidates.length} candidate{candidates.length !== 1 ? 's' : ''}</span>
          </div>
          <div style={{ padding: '1rem' }}>
            <p className="text-sm text-muted" style={{ marginBottom: '1rem' }}>
              Click a row to expand the score breakdown. Blue skill chips are exact matches.
            </p>
            <CandidateTable candidates={candidates} requiredSkills={request.required_skills} />
          </div>
        </div>
      )}
    </div>
  )
}
