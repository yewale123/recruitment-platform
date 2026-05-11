import { Link } from 'react-router-dom'

export default function HomePage() {
  return (
    <div style={{ maxWidth: 680, margin: '4rem auto', textAlign: 'center' }}>
      <h1 style={{ fontSize: '2.5rem', fontWeight: 800, letterSpacing: '-1px', color: 'var(--gray-900)', lineHeight: 1.2 }}>
        Smart Candidate Sourcing,<br />
        <span style={{ color: 'var(--primary)' }}>Fully Automated</span>
      </h1>
      <p style={{ marginTop: '1.25rem', fontSize: '1.1rem', color: 'var(--gray-600)', lineHeight: 1.7 }}>
        Describe the role you are hiring for. RecruitAI will search LinkedIn for matching candidates,
        score and rank them by suitability, and have results ready when you come back.
      </p>

      <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', marginTop: '2rem' }}>
        <Link to="/requests/new" className="btn btn-primary" style={{ padding: '.75rem 2rem', fontSize: '1rem' }}>
          Start a New Search
        </Link>
        <Link to="/requests" className="btn btn-outline" style={{ padding: '.75rem 2rem', fontSize: '1rem' }}>
          View My Requests
        </Link>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: '1.5rem', marginTop: '4rem', textAlign: 'left' }}>
        {[
          { icon: '📋', title: 'Define Requirements', desc: 'Specify skills, experience, location and keywords for the role.' },
          { icon: '🤖', title: 'Automated Sourcing', desc: 'Our scraper searches LinkedIn in the background while you do other things.' },
          { icon: '🏆', title: 'Ranked Results', desc: 'Come back later to find candidates ranked by a 100-point suitability score.' },
        ].map(({ icon, title, desc }) => (
          <div key={title} className="card" style={{ textAlign: 'left' }}>
            <div style={{ fontSize: '1.75rem', marginBottom: '.5rem' }}>{icon}</div>
            <h3 style={{ fontWeight: 700, marginBottom: '.4rem' }}>{title}</h3>
            <p className="text-sm text-muted">{desc}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
