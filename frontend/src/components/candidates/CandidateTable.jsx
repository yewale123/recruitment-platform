import { useState } from 'react'
import ScoreBar from './ScoreBar'
import ScoreBreakdown from './ScoreBreakdown'

function EmailCell({ email, status, rank, requestStatus }) {
  if (email && status === 'found') {
    return (
      <a href={`mailto:${email}`} style={{ fontSize: '.78rem', color: 'var(--primary)', wordBreak: 'break-all' }}>
        {email}
      </a>
    )
  }
  if (email && status === 'guessed') {
    return (
      <span title="Pattern-generated — not verified" style={{ fontSize: '.78rem', color: 'var(--gray-600)', wordBreak: 'break-all' }}>
        ~{email}
      </span>
    )
  }
  // Show spinner only while request is still running AND enrichment not done yet
  if (rank <= 10 && !status && requestStatus !== 'completed' && requestStatus !== 'failed') {
    return <span className="spinner" style={{ width: 12, height: 12, borderWidth: 2 }} />
  }
  return <span className="text-muted">—</span>
}

export default function CandidateTable({ candidates, requiredSkills = [], requestStatus = 'completed' }) {
  const [expandedId, setExpandedId] = useState(null)
  const [sortKey, setSortKey] = useState('rank')
  const [sortDir, setSortDir] = useState('asc')
  const [platformFilter, setPlatformFilter] = useState('all')

  const normalizedRequired = requiredSkills.map(s => s.toLowerCase())

  const platforms = ['all', ...new Set(candidates.map(c => c.platform))]

  const filtered = candidates.filter(c => platformFilter === 'all' || c.platform === platformFilter)

  const sorted = [...filtered].sort((a, b) => {
    let av = a[sortKey], bv = b[sortKey]
    if (av == null) av = sortDir === 'asc' ? Infinity : -Infinity
    if (bv == null) bv = sortDir === 'asc' ? Infinity : -Infinity
    return sortDir === 'asc' ? (av > bv ? 1 : -1) : (av < bv ? 1 : -1)
  })

  function handleSort(key) {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('asc') }
  }

  function arrow(key) {
    if (sortKey !== key) return ' ↕'
    return sortDir === 'asc' ? ' ↑' : ' ↓'
  }

  if (!candidates.length) {
    return <p className="text-muted" style={{ padding: '2rem', textAlign: 'center' }}>No candidates found.</p>
  }

  return (
    <div>
      {platforms.length > 2 && (
        <div className="tabs">
          {platforms.map(p => (
            <button key={p} className={`tab ${platformFilter === p ? 'active' : ''}`} onClick={() => setPlatformFilter(p)}>
              {p === 'all' ? 'All Platforms' : p.charAt(0).toUpperCase() + p.slice(1)}
            </button>
          ))}
        </div>
      )}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th onClick={() => handleSort('rank')}>Rank{arrow('rank')}</th>
              <th>Name &amp; Headline</th>
              <th>Location</th>
              <th onClick={() => handleSort('experience_years')}>Exp{arrow('experience_years')}</th>
              <th>Skills</th>
              <th onClick={() => handleSort('suitability_score')}>Score{arrow('suitability_score')}</th>
              <th>Email</th>
              <th>Profile</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map(c => (
              <>
                <tr key={c.id} onClick={() => setExpandedId(expandedId === c.id ? null : c.id)} style={{ cursor: 'pointer' }}>
                  <td>
                    <span style={{ fontWeight: 700, color: c.rank <= 3 ? 'var(--primary)' : undefined }}>
                      #{c.rank ?? '—'}
                    </span>
                  </td>
                  <td>
                    <div style={{ fontWeight: 600 }}>{c.full_name || '—'}</div>
                    <div className="text-sm text-muted">{c.headline || '—'}</div>
                  </td>
                  <td className="text-sm">{c.location || '—'}</td>
                  <td className="text-sm">
                    {c.experience_years != null ? `${c.experience_years} yrs` : '—'}
                  </td>
                  <td>
                    <div className="chips">
                      {(c.skills || []).slice(0, 5).map(s => (
                        <span key={s} className={`chip ${normalizedRequired.includes(s.toLowerCase()) ? 'matched' : ''}`}>
                          {s}
                        </span>
                      ))}
                      {(c.skills || []).length > 5 && (
                        <span className="chip">+{c.skills.length - 5}</span>
                      )}
                    </div>
                  </td>
                  <td style={{ minWidth: 140 }}>
                    <ScoreBar score={c.suitability_score} />
                  </td>
                  <td onClick={e => e.stopPropagation()}>
                    <EmailCell email={c.email} status={c.email_status} rank={c.rank} requestStatus={requestStatus} />
                  </td>
                  <td>
                    {c.profile_url
                      ? <a href={c.profile_url} target="_blank" rel="noreferrer" onClick={e => e.stopPropagation()} className="btn btn-outline btn-sm">View</a>
                      : '—'}
                  </td>
                </tr>
                {expandedId === c.id && (
                  <tr key={`${c.id}-breakdown`}>
                    <td colSpan={8} style={{ padding: 0 }}>
                      <ScoreBreakdown breakdown={c.score_breakdown} />
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
