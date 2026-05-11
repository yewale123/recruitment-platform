export default function StatusBadge({ status }) {
  const icons = { pending: '⏳', running: '⚙️', completed: '✓', failed: '✗' }
  return (
    <span className={`badge badge-${status}`}>
      {icons[status] || ''} {status}
    </span>
  )
}
