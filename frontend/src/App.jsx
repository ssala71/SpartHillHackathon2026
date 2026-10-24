import { useEffect, useState } from 'react'
import AppLayout from '@cloudscape-design/components/app-layout'
import Flashbar from '@cloudscape-design/components/flashbar'
import SideNavigation from '@cloudscape-design/components/side-navigation'
import TopNavigation from '@cloudscape-design/components/top-navigation'
import { USING_MOCK } from './api/client.js'
import logoUrl from './assets/waypoint.svg'
import { DataProvider, useData } from './hooks/DataContext.jsx'
import { getMode, setMode } from './theme.js'
import OverviewPage from './pages/OverviewPage.jsx'
import RequestsPage from './pages/RequestsPage.jsx'
import ResourcesPage from './pages/ResourcesPage.jsx'
import IncidentsPage from './pages/IncidentsPage.jsx'
import AssignmentsPage from './pages/AssignmentsPage.jsx'
import SimulatorPage from './pages/SimulatorPage.jsx'
import HowItWorksPage from './pages/HowItWorksPage.jsx'

// Console pages, keyed by their #/hash.
const PAGES = {
  demo: { title: 'Live demo', component: SimulatorPage },
  overview: { title: 'Overview', component: OverviewPage },
  requests: { title: 'Requests', component: RequestsPage },
  incidents: { title: 'Incidents and alerts', component: IncidentsPage },
  resources: { title: 'Resources and inventory', component: ResourcesPage },
  assignments: { title: 'Assignments', component: AssignmentsPage },
  'how-it-works': { title: 'How it works', component: HowItWorksPage },
}

const currentPage = () => {
  const key = window.location.hash.replace('#/', '')
  return PAGES[key] ? key : 'demo'
}

function useHashPage() {
  const [page, setPage] = useState(currentPage)
  useEffect(() => {
    const onHashChange = () => setPage(currentPage())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])
  useEffect(() => {
    document.title = `${PAGES[page].title} · Waypoint`
    window.scrollTo(0, 0)
  }, [page])
  return page
}

function Console({ page }) {
  const [splitPanel, setSplitPanel] = useState(null)
  const [mode, setModeState] = useState(getMode)
  const { flashes, requests } = useData()

  // Close any open detail panel when moving between pages.
  const [panelPage, setPanelPage] = useState(page)
  if (panelPage !== page) {
    setPanelPage(page)
    setSplitPanel(null)
  }

  const toggleMode = () => {
    const next = mode === 'dark' ? 'light' : 'dark'
    setMode(next)
    setModeState(next)
  }

  const reviewCount = requests.filter((r) => r.status === 'NeedsReview' || r.processing_error).length
  const Page = PAGES[page].component

  return (
    <>
      <div id="top-nav">
        <TopNavigation
          identity={{ href: '#/demo', title: 'Waypoint', logo: { src: logoUrl, alt: 'Waypoint' } }}
          utilities={[
            {
              type: 'button',
              text: USING_MOCK ? 'Demo data' : 'Live',
              iconName: USING_MOCK ? 'status-pending' : 'status-positive',
              title: USING_MOCK ? 'Showing simulated data. Set VITE_API_BASE_URL to use the backend.' : 'Connected to the Waypoint API',
            },
            {
              type: 'button',
              text: mode === 'dark' ? 'Light mode' : 'Dark mode',
              onClick: toggleMode,
            },
          ]}
        />
      </div>
      <AppLayout
        headerSelector="#top-nav"
        toolsHide
        navigation={
          <SideNavigation
            activeHref={`#/${page}`}
            header={{ href: '#/demo', text: 'Waypoint' }}
            items={[
              { type: 'link', text: 'Live demo', href: '#/demo' },
              { type: 'divider' },
              { type: 'link', text: 'Overview', href: '#/overview' },
              {
                type: 'link',
                text: 'Requests',
                href: '#/requests',
                info: reviewCount ? <span>{reviewCount} to review</span> : undefined,
              },
              { type: 'link', text: 'Incidents and alerts', href: '#/incidents' },
              { type: 'link', text: 'Resources and inventory', href: '#/resources' },
              { type: 'link', text: 'Assignments', href: '#/assignments' },
              { type: 'divider' },
              { type: 'link', text: 'How it works', href: '#/how-it-works' },
            ]}
          />
        }
        notifications={<Flashbar items={flashes} stackItems />}
        splitPanel={splitPanel?.content}
        splitPanelOpen={Boolean(splitPanel)}
        onSplitPanelToggle={({ detail }) => !detail.open && setSplitPanel(null)}
        splitPanelPreferences={{ position: 'side' }}
        content={<Page setSplitPanel={setSplitPanel} />}
      />
    </>
  )
}

export default function App() {
  const page = useHashPage()
  return (
    <DataProvider>
      <Console page={page} />
    </DataProvider>
  )
}
