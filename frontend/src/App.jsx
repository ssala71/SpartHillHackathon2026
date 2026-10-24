import { useEffect, useState } from 'react'
import AppLayout from '@cloudscape-design/components/app-layout'
import Flashbar from '@cloudscape-design/components/flashbar'
import SideNavigation from '@cloudscape-design/components/side-navigation'
import TopNavigation from '@cloudscape-design/components/top-navigation'
import Alert from '@cloudscape-design/components/alert'
import { USING_MOCK } from './api/client.js'
import logoUrl from './assets/waypoint.svg'
import { DataProvider, useData } from './hooks/DataContext.jsx'
import OverviewPage from './pages/OverviewPage.jsx'
import RequestsPage from './pages/RequestsPage.jsx'
import ResourcesPage from './pages/ResourcesPage.jsx'
import IncidentsPage from './pages/IncidentsPage.jsx'
import AssignmentsPage from './pages/AssignmentsPage.jsx'
import SimulatorPage from './pages/SimulatorPage.jsx'
import HowItWorksPage from './pages/HowItWorksPage.jsx'

const PAGES = {
  overview: { title: 'Overview', component: OverviewPage },
  requests: { title: 'Requests', component: RequestsPage },
  incidents: { title: 'Incidents and alerts', component: IncidentsPage },
  resources: { title: 'Resources and inventory', component: ResourcesPage },
  assignments: { title: 'Assignments', component: AssignmentsPage },
  simulator: { title: 'SMS simulator', component: SimulatorPage },
  'how-it-works': { title: 'How it works', component: HowItWorksPage },
}

const currentPage = () => {
  const key = window.location.hash.replace('#/', '')
  return PAGES[key] ? key : 'overview'
}

function Shell() {
  const [page, setPage] = useState(currentPage)
  const [splitPanel, setSplitPanel] = useState(null)
  const { flashes, requests } = useData()

  useEffect(() => {
    const onHashChange = () => {
      setPage(currentPage())
      setSplitPanel(null)
    }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  const reviewCount = requests.filter((r) => r.status === 'NeedsReview' || r.processing_error).length
  const Page = PAGES[page].component

  return (
    <>
      <div id="top-nav">
        <TopNavigation
          identity={{ href: '#/overview', title: 'Waypoint', logo: { src: logoUrl, alt: 'Waypoint' } }}
          utilities={[{ type: 'button', text: USING_MOCK ? 'Demo data' : 'Live API', iconName: USING_MOCK ? 'status-pending' : 'status-positive' }]}
        />
      </div>
      <AppLayout
        headerSelector="#top-nav"
        toolsHide
        navigation={
          <SideNavigation
            activeHref={`#/${page}`}
            header={{ href: '#/overview', text: 'Coordinator console' }}
            items={[
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
              {
                type: 'section',
                text: 'Demo',
                items: [
                  { type: 'link', text: 'SMS simulator', href: '#/simulator' },
                  { type: 'link', text: 'How it works', href: '#/how-it-works' },
                ],
              },
            ]}
          />
        }
        notifications={
          <>
            {USING_MOCK && (
              <Alert type="info" statusIconAriaLabel="Info">
                Showing simulated demo data. Set VITE_API_BASE_URL to connect to the backend.
              </Alert>
            )}
            <Flashbar items={flashes} />
          </>
        }
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
  return (
    <DataProvider>
      <Shell />
    </DataProvider>
  )
}
