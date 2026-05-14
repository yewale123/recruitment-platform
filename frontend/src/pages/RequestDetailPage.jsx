import { useState, useEffect, useRef } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useRequest } from '../hooks/useRequest'
import StatusBadge from '../components/requests/StatusBadge'
import CandidateTable from '../components/candidates/CandidateTable'
import { formatDateTime } from '../utils/formatters'
import { deleteRequest } from '../api/client'

// ── Progress tracker component ────────────────────────────────────────────────

function ProgressTracker({ request, elapsed }) {
  const jobs = request.scrape_jobs || []
  const anyJobRunning = jobs.some(j => j.status === 'running')
  const anyJobDone = jobs.some(j => j.status === 'completed' || j.status === 'failed')
  const allJobsDone = jobs.length > 0 && jobs.every(j => j.status === 'completed' || j.status === 'failed')

  // Derive current step (1=queued/queries, 2=scraping, 3=scoring)
  let currentStep = 1
  if (anyJobRunning || anyJobDone) currentStep = 2
  if (allJobsDone && request.status === 'running') currentStep = 3

  // Asymptotic progress fill — reaches ~63% at 45s, ~86% at 90s, caps at 95%
  const fillPct = request.status === 'completed'
    ? 100
    : Math.min(95, Math.round(100 * (1 - Math.exp(-elapsed / 50))))

  const steps = [
    {
      label: 'Generating search queries',
      sub: 'Building smart queries using AI + synonyms',
      done: currentStep > 1,
      active: currentStep === 1,
    },
    {
      label: 'Scraping candidates',
      sub: null,
      done: currentStep > 2,
      active: currentStep === 2,
    },
    {
      label: 'Scoring & ranking',
      sub: 'Matching skills, experience, location and seniority',
      done: request.status === 'completed',
      active: currentStep === 3,
    },
  ]

  return (
    <div className="card" style={{ marginBottom: '1.5rem', borderLeft: '4px solid var(--primary)' }}>
      {/* Header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <span className="spinner" />
          <strong style={{ fontSize: '1rem' }}>Finding candidates…</strong>
        </div>
        <span className="text-sm text-muted" style={{ whiteSpace: 'nowrap' }}>
          {elapsed}s &nbsp;·&nbsp; ~60s expected
        </span>
      </div>

      {/* Progress bar */}
      <div style={{ background: 'var(--gray-100)', borderRadius: 999, height: 7, marginBottom: '1.25rem', overflow: 'hidden' }}>
        <div style={{
          height: '100%',
          width: `${fillPct}%`,
          background: 'linear-gradient(90deg, var(--primary), #60a5fa)',
          borderRadius: 999,
          transition: 'width 2s ease',
        }} />
      </div>

      {/* Steps */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
        {steps.map((step, i) => (
          <div key={i}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <StepIcon done={step.done} active={step.active} />
              <span style={{
                fontWeight: step.active ? 700 : 400,
                color: step.done ? 'var(--gray-600)' : step.active ? 'var(--gray-900)' : 'var(--gray-400)',
                fontSize: '.9rem',
              }}>
                {step.label}
              </span>
              {step.active && <span className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />}
            </div>

            {/* Sub-label */}
            {step.sub && (step.done || step.active) && (
              <p className="text-sm text-muted" style={{ marginLeft: '1.6rem', marginTop: '0.15rem' }}>
                {step.sub}
              </p>
            )}

            {/* Per-platform rows under step 2 */}
            {i === 1 && (step.active || step.done) && jobs.map(job => (
              <div key={job.id} style={{ marginLeft: '1.6rem', marginTop: '0.35rem', display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                <span style={{ fontWeight: 600, textTransform: 'capitalize', fontSize: '.85rem', width: 70 }}>{job.platform}</span>
                <StatusBadge status={job.status} />
                {job.candidates_found > 0 && (
                  <span className="text-sm" style={{ color: 'var(--success)', fontWeight: 600 }}>
                    {job.candidates_found} found
                  </span>
                )}
                {job.status === 'failed' && job.error_message && (
                  <span className="text-sm" style={{ color: 'var(--danger)' }}>
                    {job.error_message.split('\n')[0].slice(0, 80)}
                  </span>
                )}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

function StepIcon({ done, active }) {
  const color = done ? 'var(--success)' : active ? 'var(--primary)' : 'var(--gray-300)'
  return (
    <span style={{
      width: 20, height: 20, borderRadius: '50%',
      background: done ? 'var(--success)' : active ? 'var(--primary-light)' : 'var(--gray-100)',
      border: `2px solid ${color}`,
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      flexShrink: 0, fontSize: '.65rem', fontWeight: 800, color,
    }}>
      {done ? '✓' : ''}
    </span>
  )
}

// ── Main page ────────────────────────────────────────────────────────────────

export default function RequestDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [deleting, setDeleting] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const startRef = useRef(Date.now())
  const { request, candidates, isLoading, error } = useRequest(Number(id))

  // Elapsed-second counter — ticks while request is in-flight
  useEffect(() => {
    if (!request) return
    if (request.status === 'completed' || request.status === 'failed') return
    const t = setInterval(() => setElapsed(Math.floor((Date.now() - startRef.current) / 1000)), 1000)
    return () => clearInterval(t)
  }, [request?.status])

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

  const isRunning = request.status === 'pending' || request.status === 'running'

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
              {request.experience_min}{request.experience_max ? `–${request.experience_max}` : '+'} years
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

      {/* Live progress tracker */}
      {isRunning && <ProgressTracker request={request} elapsed={elapsed} />}

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

      {/* Candidates — shown when completed, or partially while running */}
      {candidates.length > 0 && (
        <div className="card" style={{ padding: 0 }}>
          <div style={{ padding: '1rem 1.5rem', borderBottom: '1.5px solid var(--gray-100)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ fontWeight: 700 }}>
              {request.status === 'completed' ? 'Ranked Candidates' : 'Candidates Found So Far'}
            </h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              {isRunning && <span className="spinner" style={{ width: 16, height: 16 }} />}
              <span className="text-sm text-muted">{candidates.length} candidate{candidates.length !== 1 ? 's' : ''}</span>
            </div>
          </div>
          <div style={{ padding: '1rem' }}>
            {isRunning && (
              <p className="text-sm text-muted" style={{ marginBottom: '1rem' }}>
                Showing partial results — more may arrive as other platforms finish.
              </p>
            )}
            {!isRunning && (
              <p className="text-sm text-muted" style={{ marginBottom: '1rem' }}>
                Click a row to expand the score breakdown. Blue chips are matched skills.
              </p>
            )}
            <CandidateTable candidates={candidates} requiredSkills={request.required_skills} />
          </div>
        </div>
      )}

      {/* Empty state when completed with no results */}
      {request.status === 'completed' && candidates.length === 0 && (
        <div className="card" style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--gray-400)' }}>
          <p style={{ fontSize: '1.1rem', marginBottom: '0.5rem' }}>No candidates found</p>
          <p className="text-sm">Try broadening the skills, location, or experience range.</p>
        </div>
      )}
    </div>
  )
}
