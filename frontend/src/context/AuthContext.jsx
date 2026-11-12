import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

import { setUnauthorizedHandler, tokenStore } from '../api/client'
import { authApi } from '../api/endpoints'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [status, setStatus] = useState(() => (tokenStore.get() ? 'loading' : 'anonymous'))

  const logout = useCallback(() => {
    tokenStore.clear()
    setUser(null)
    setStatus('anonymous')
  }, [])

  // Any 401 from the API (expired/invalid token) signs the user out.
  useEffect(() => setUnauthorizedHandler(logout), [logout])

  // Restore the session on page load if a token is present.
  useEffect(() => {
    if (!tokenStore.get()) return
    authApi
      .me()
      .then((me) => {
        setUser(me)
        setStatus('authenticated')
      })
      .catch(logout)
  }, [logout])

  const login = useCallback(async (email, password) => {
    const data = await authApi.login(email, password)
    tokenStore.set(data.access_token)
    setUser(data.user)
    setStatus('authenticated')
    return data.user
  }, [])

  const value = useMemo(
    () => ({
      user,
      status,
      login,
      logout,
      hasRole: (...roles) => Boolean(user && roles.includes(user.role)),
    }),
    [user, status, login, logout],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>')
  return context
}
