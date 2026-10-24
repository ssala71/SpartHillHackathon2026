import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api } from '../api/client.js'

const DataContext = createContext(null)

const EMPTY = { incidents: [], requests: [], resources: [], inventory: [], assignments: [] }

export function DataProvider({ children }) {
  const [data, setData] = useState(EMPTY)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [flashes, setFlashes] = useState([])

  const refresh = useCallback(async () => {
    try {
      const [incidents, requests, resources, inventory, assignments] = await Promise.all([
        api.listIncidents(),
        api.listRequests(),
        api.listResources(),
        api.listInventory(),
        api.listAssignments(),
      ])
      setData({ incidents, requests, resources, inventory, assignments })
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    // Initial load from the API; state updates happen after the awaited calls.
    // oxlint-disable-next-line react/set-state-in-effect
    refresh()
  }, [refresh])

  const notify = useCallback((type, content) => {
    const id = crypto.randomUUID()
    const dismiss = () => setFlashes((items) => items.filter((item) => item.id !== id))
    setFlashes((items) => [{ id, type, content, dismissible: true, onDismiss: dismiss }, ...items].slice(0, 3))
    if (type === 'success') setTimeout(dismiss, 5000)
  }, [])

  // Runs a change against the API, then reloads everything and reports the outcome.
  const run = useCallback(
    async (action, successMessage) => {
      try {
        const result = await action(api)
        await refresh()
        if (successMessage) notify('success', successMessage)
        return result
      } catch (err) {
        notify('error', err.message)
        return null
      }
    },
    [refresh, notify],
  )

  return (
    <DataContext.Provider value={{ ...data, loading, error, refresh, run, flashes }}>{children}</DataContext.Provider>
  )
}

// eslint-disable-next-line react/only-export-components
export const useData = () => useContext(DataContext)
