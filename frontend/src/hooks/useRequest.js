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
  const emailsDoneRef = useRef(false)

  const stopPolling = useCallback(() => {
    setIsPolling(false)
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }, [])

  const fetchAll = useCallback(async () => {
    try {
      const req = await getRequest(id)
      setRequest(req)

      const hasPartial = req.scrape_jobs?.some(j => j.candidates_found > 0)
      let latestCandidates = null
      if (req.status === 'completed' || hasPartial) {
        const cands = await getCandidates(id)
        latestCandidates = cands.items
        setCandidates(cands.items)
      }

      setError(null)

      if (TERMINAL.has(req.status)) {
        const emailsPending = (latestCandidates ?? []).some(
          c => c.rank != null && c.rank <= 10 && c.email_status == null
        )
        if (!emailsPending) {
          emailsDoneRef.current = true
          stopPolling()
        }
        // else: keep polling until emails are resolved
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setIsLoading(false)
    }
  }, [id, stopPolling])

  useEffect(() => {
    fetchAll()
  }, [fetchAll])

  useEffect(() => {
    if (!request) return
    // Don't start a new interval if emails are already done
    if (TERMINAL.has(request.status) && emailsDoneRef.current) return
    if (intervalRef.current) return

    setIsPolling(true)
    intervalRef.current = setInterval(fetchAll, POLL_INTERVAL)

    return () => {
      // Only clear if emails are done — otherwise keep polling through status change
      if (emailsDoneRef.current && intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [request?.status, fetchAll])

  return { request, candidates, isLoading, isPolling, error }
}
