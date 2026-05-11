import { useState, useEffect, useCallback } from 'react'
import { listRequests } from '../api/client'

export function useRequests() {
  const [requests, setRequests] = useState([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetch = useCallback(async () => {
    try {
      const data = await listRequests()
      setRequests(data.items)
      setTotal(data.total)
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetch()

    // Auto-refresh every 10s if any request is still active
    const interval = setInterval(() => {
      const hasActive = requests.some(r => r.status === 'pending' || r.status === 'running')
      if (hasActive) fetch()
    }, 10_000)

    return () => clearInterval(interval)
  }, [fetch, requests.length])

  return { requests, total, isLoading, error, refetch: fetch }
}
