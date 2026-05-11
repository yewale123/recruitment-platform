import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

// ── Requests ──────────────────────────────────────────────────────────────────

export const createRequest = (data) => api.post('/requests', data).then(r => r.data)

export const listRequests = (params = {}) => api.get('/requests', { params }).then(r => r.data)

export const getRequest = (id) => api.get(`/requests/${id}`).then(r => r.data)

export const deleteRequest = (id) => api.delete(`/requests/${id}`)

// ── Candidates ────────────────────────────────────────────────────────────────

export const getCandidates = (requestId, params = {}) =>
  api.get(`/requests/${requestId}/candidates`, { params }).then(r => r.data)

// ── Health ────────────────────────────────────────────────────────────────────

export const getHealth = () => api.get('/health').then(r => r.data)

export default api
