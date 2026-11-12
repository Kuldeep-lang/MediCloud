import axios from 'axios'

const TOKEN_KEY = 'medicloud.token'

/** Token lives in sessionStorage (cleared when the tab closes). Storage may be blocked. */
export const tokenStore = {
  get() {
    try {
      return sessionStorage.getItem(TOKEN_KEY)
    } catch {
      return null
    }
  },
  set(token) {
    try {
      sessionStorage.setItem(TOKEN_KEY, token)
    } catch {
      /* storage unavailable - session lasts until reload */
    }
  },
  clear() {
    try {
      sessionStorage.removeItem(TOKEN_KEY)
    } catch {
      /* ignore */
    }
  },
}

// Relative base URL: the same bundle works behind Vite, nginx or a Kubernetes Ingress.
export const api = axios.create({ baseURL: '/api/v1', timeout: 15000 })

api.interceptors.request.use((config) => {
  const token = tokenStore.get()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

let unauthorizedHandler = () => {}
export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler
}

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const isLogin = error.config?.url?.includes('/auth/login')
    if (error.response?.status === 401 && !isLogin) unauthorizedHandler()
    return Promise.reject(error)
  },
)

/** Turn any API error into a human-readable message. */
export function errorMessage(error, fallback = 'Something went wrong. Please try again.') {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length) {
    return detail
      .map((d) => {
        const field = Array.isArray(d.loc) ? d.loc[d.loc.length - 1] : ''
        return field ? `${String(field).replaceAll('_', ' ')}: ${d.msg}` : d.msg
      })
      .join('; ')
  }
  if (error?.code === 'ECONNABORTED') return 'The server took too long to respond.'
  if (error && !error.response) return 'Cannot reach the server. Check that the backend is running.'
  return fallback
}
