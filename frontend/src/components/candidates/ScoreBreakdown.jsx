import ScoreBar from './ScoreBar'

const DIMS = [
  { key: 'skills_score',     label: 'Skills',     max: 40 },
  { key: 'experience_score', label: 'Experience',  max: 25 },
  { key: 'location_score',   label: 'Location',    max: 20 },
  { key: 'keywords_score',   label: 'Keywords',    max: 15 },
]

export default function ScoreBreakdown({ breakdown }) {
  if (!breakdown) return null
  return (
    <div className="breakdown-grid">
      {DIMS.map(({ key, label, max }) => (
        <div key={key} className="breakdown-row">
          <span className="breakdown-label">{label} (/{max})</span>
          <ScoreBar score={breakdown[key]} max={max} />
        </div>
      ))}
    </div>
  )
}
