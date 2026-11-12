import { createContext, useContext, useEffect, useState } from 'react'

import { systemApi } from '../api/endpoints'
import { configureFormatting } from '../utils/format'

const DEFAULT_INFO = { app: 'MediCloud', version: '', currency: 'INR', timezone: 'Asia/Kolkata' }
const AppInfoContext = createContext(DEFAULT_INFO)

/** Loads public app info (currency, time zone, version) once at start-up. */
export function AppInfoProvider({ children }) {
  const [info, setInfo] = useState(DEFAULT_INFO)
  useEffect(() => {
    systemApi
      .info()
      .then((data) => {
        configureFormatting(data)
        setInfo(data)
      })
      .catch(() => {
        /* keep defaults - the login page still works */
      })
  }, [])
  return <AppInfoContext.Provider value={info}>{children}</AppInfoContext.Provider>
}

export function useAppInfo() {
  return useContext(AppInfoContext)
}
