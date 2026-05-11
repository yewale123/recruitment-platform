import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import RequestForm from '../components/requests/RequestForm'
import { createRequest } from '../api/client'

export default function NewRequestPage() {
  const navigate = useNavigate()
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(payload) {
    setIsSubmitting(true)
    setError(null)
    try {
      const req = await createRequest(payload)
      navigate(`/requests/${req.id}`)
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Something went wrong')
      setIsSubmitting(false)
    }
  }

  return (
    <div style={{ maxWidth: 640, margin: '0 auto' }}>
      <h2 style={{ fontWeight: 800, fontSize: '1.5rem', marginBottom: '.5rem' }}>New Recruitment Request</h2>
      <p className="text-muted text-sm" style={{ marginBottom: '1.5rem' }}>
        Fill in the details below. We will search LinkedIn and rank matching candidates in the background.
      </p>

      {error && (
        <div style={{ padding: '1rem', background: '#fee2e2', borderRadius: 'var(--radius)', color: 'var(--danger)', marginBottom: '1rem', fontSize: '.875rem' }}>
          {error}
        </div>
      )}

      <div className="card">
        <RequestForm onSubmit={handleSubmit} isSubmitting={isSubmitting} />
      </div>
    </div>
  )
}
