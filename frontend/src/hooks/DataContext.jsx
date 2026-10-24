import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import Button from '@cloudscape-design/components/button'
import { api, USING_MOCK } from '../api/client.js'

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
    // New texts reach the backend on their own, so check for them every few seconds.
    if (USING_MOCK) return undefined
    const timer = setInterval(refresh, 5000)
    return () => clearInterval(timer)
  }, [refresh])

  const notify = useCallback((type, content, undo) => {
    const id = crypto.randomUUID()
    const dismiss = () => setFlashes((items) => items.filter((item) => item.id !== id))
    const action = undo ? (
      <Button
        onClick={() => {
          dismiss()
          undo()
        }}
      >
        Undo
      </Button>
    ) : undefined
    setFlashes((items) => [{ id, type, content, action, dismissible: true, onDismiss: dismiss }, ...items].slice(0, 1))
    if (type === 'success') setTimeout(dismiss, undo ? 10000 : 5000)
  }, [])

  // Runs a change against the API, then reloads everything and reports the outcome.
  // Pass `undo` ((api, result) => Promise) to offer an Undo button on the confirmation.
  const run = useCallback(
    async (action, successMessage, undo) => {
      try {
        const result = await action(api)
        await refresh()
        if (successMessage) {
          const undoIt = undo
            ? async () => {
                try {
                  await undo(api, result)
                  await refresh()
                  notify('success', 'Undone.')
                } catch (err) {
                  notify('error', `Couldn't undo: ${err.message}`)
                }
              }
            : undefined
          notify('success', successMessage, undoIt)
        }
        return result
      } catch (err) {
        notify('error', err.message)
        return null
      }
    },
    [refresh, notify],
  )

  return <DataContext.Provider value={{ ...data, loading, error, refresh, run, flashes }}>{children}</DataContext.Provider>
}

// eslint-disable-next-line react/only-export-components
export const useData = () => useContext(DataContext)
