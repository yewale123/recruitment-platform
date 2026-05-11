import { useState, useEffect, useRef, useCallback } from 'react'
import { getRequest, getCandidates } from '../api/client'

const TERMINAL = new Set(['completed', 'failed'])
const POLL_INTERVAL = 5_000

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

      if (req.status === 'completed') {
        const cands = await getCandidates(id)
        setCandidates(cands.items)
      }

      setError(null)

      // Stop polling when terminal state is reached
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

  // Start polling once request is loaded and not yet in terminal state
  useEffect(() => {
    if (!request) return
    if (TERMINAL.has(request.status)) return
    if (intervalRef.current) return  // already polling

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
