import { useState, useEffect, useRef, useCallback } from 'react'
import { getRequest, getCandidates } from '../api/client'

const TERMINAL = new Set(['completed', 'failed'])
const POLL_MS = 3_000

export function useRequest(id) {
  const [request, setRequest] = useState(null)
  const [candidates, setCandidates] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [isPolling, setIsPolling] = useState(false)
  const [error, setError] = useState(null)
  const intervalRef = useRef(null)

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    setIsPolling(false)
  }, [])

  const fetchAll = useCallback(async () => {
    try {
      const req = await getRequest(id)
      setRequest(req)

      const hasPartial = req.scrape_jobs?.some(j => j.candidates_found > 0)
      if (req.status === 'completed' || hasPartial) {
        const res = await getCandidates(id)
        setCandidates(res.items)
      }

      setError(null)

      if (TERMINAL.has(req.status)) {
        stopPolling()
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setIsLoading(false)
    }
  }, [id, stopPolling])

  useEffect(() => {
    fetchAll()
    intervalRef.current = setInterval(fetchAll, POLL_MS)
    setIsPolling(true)
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [fetchAll])

  return { request, candidates, isLoading, isPolling, error }
}
