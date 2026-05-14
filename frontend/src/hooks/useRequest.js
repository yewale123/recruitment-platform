import { useState, useEffect, useRef, useCallback } from 'react'
import { getRequest, getCandidates } from '../api/client'

const TERMINAL = new Set(['completed', 'failed'])
const POLL_INTERVAL = 3_000

export function useRequest(id) {
  const [request, setRequest] = useState(null)
  const [candidates, setCandidates] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [isPolling, setIsPolling] = useState(false)
  const [error, setError] = useState(null)
  const intervalRef = useRef(null)

  const fetchAll = useCallback(async () => {
    try {
      const req = await getRequest(id)
      setRequest(req)

      // Fetch candidates when completed, OR when any job has found some (partial results)
      const hasPartial = req.scrape_jobs?.some(j => j.candidates_found > 0)
      if (req.status === 'completed' || hasPartial) {
        const cands = await getCandidates(id)
        setCandidates(cands.items)
      }

      setError(null)

      if (TERMINAL.has(req.status)) {
        setIsPolling(false)
        if (intervalRef.current) {
          clearInterval(intervalRef.current)
          intervalRef.current = null
        }
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setIsLoading(false)
    }
  }, [id])

  useEffect(() => {
    fetchAll()
  }, [fetchAll])

  useEffect(() => {
    if (!request) return
    if (TERMINAL.has(request.status)) return
    if (intervalRef.current) return

    setIsPolling(true)
    intervalRef.current = setInterval(fetchAll, POLL_INTERVAL)

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [request?.status, fetchAll])

  return { request, candidates, isLoading, isPolling, error }
}
