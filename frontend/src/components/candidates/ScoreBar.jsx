import { scoreColor } from '../../utils/formatters'

export default function ScoreBar({ score, max = 100, showLabel = true }) {
  if (score == null) return <span className="text-muted text-sm">—</span>
  const pct = Math.min(100, (score / max) * 100)
  const color = scoreColor(score)

  return (
    <div className="score-bar-wrap">
      <div className="score-bar-track">
        <div className={`score-bar-fill ${color}`} style={{ width: `${pct}%` }} />
      </div>
      {showLabel && (
        <span className={`score-label score-label--${color}`}>
          {score.toFixed(0)}
        </span>
      )}
    </div>
  )
}
