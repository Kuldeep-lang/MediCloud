import { useCallback, useEffect, useRef, useState } from 'react'

import { errorMessage } from '../api/client'

/**
 * Fetch data whenever `deps` change.
 * - Keeps the previous data while refetching (no skeleton flash, no layout jump).
 * - Ignores responses from superseded requests.
 */
export function useApi(fetcher, deps = [], { enabled = true } = {}) {
  const fetcherRef = useRef(fetcher)
  useEffect(() => {
    fetcherRef.current = fetcher
  })

  const [reloadCount, setReloadCount] = useState(0)
  const key = enabled ? JSON.stringify([deps, reloadCount]) : null
  const [result, setResult] = useState({ key: undefined, data: null, error: null })

  useEffect(() => {
    if (key === null) return undefined
    let active = true
    Promise.resolve()
      .then(() => fetcherRef.current())
      .then(
        (data) => active && setResult({ key, data, error: null }),
        (err) => active && setResult((prev) => ({ key, data: prev.data, error: errorMessage(err) })),
      )
    return () => {
      active = false
    }
  }, [key])

  const reload = useCallback(() => setReloadCount((n) => n + 1), [])
  const loading = key !== null && result.key !== key
  return {
    data: result.data,
    error: loading ? null : result.error,
    loading,
    initialLoading: loading && result.data === null,
    reload,
  }
}
