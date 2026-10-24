import { useEffect, useState } from 'react'
import AppLayout from '@cloudscape-design/components/app-layout'
import Flashbar from '@cloudscape-design/components/flashbar'
import SideNavigation from '@cloudscape-design/components/side-navigation'
import { DataProvider, useData } from './hooks/DataContext.jsx'
import TopBar from './components/TopBar.jsx'
import OverviewPage from './pages/OverviewPage.jsx'
import RequestsPage from './pages/RequestsPage.jsx'
import ResourcesPage from './pages/ResourcesPage.jsx'
import IncidentsPage from './pages/IncidentsPage.jsx'
import AssignmentsPage from './pages/AssignmentsPage.jsx'
import DemoPage from './pages/DemoPage.jsx'
import HowItWorksPage from './pages/HowItWorksPage.jsx'

// Admin pages, keyed by their #/admin/<key> hash. Anything else shows the public demo.
const PAGES = {
  overview: { title: 'Overview', component: OverviewPage },
  requests: { title: 'Requests', component: RequestsPage },
  incidents: { title: 'Incidents and alerts', component: IncidentsPage },
  resources: { title: 'Resources and inventory', component: ResourcesPage },
  assignments: { title: 'Assignments', component: AssignmentsPage },
  'how-it-works': { title: 'How it works', component: HowItWorksPage },
}

const currentPage = () => {
  const match = window.location.hash.match(/^#\/admin(?:\/([\w-]+))?/)
  if (!match) return 'demo'
  return PAGES[match[1]] ? match[1] : 'overview'
}

function useHashPage() {
  const [page, setPage] = useState(currentPage)
  useEffect(() => {
    const onHashChange = () => setPage(currentPage())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])
  useEffect(() => {
    document.title = page === 'demo' ? 'Waypoint' : `${PAGES[page].title} · Waypoint Admin`
    window.scrollTo(0, 0)
  }, [page])
  return page
}

function Console({ page }) {
  const [splitPanel, setSplitPanel] = useState(null)
  const { flashes, requests } = useData()

  // Close any open detail panel when moving between pages.
  const [panelPage, setPanelPage] = useState(page)
  if (panelPage !== page) {
    setPanelPage(page)
    setSplitPanel(null)
  }

  const reviewCount = requests.filter((r) => r.status === 'NeedsReview' || r.processing_error).length
  const Page = PAGES[page].component

  return (
    <AppLayout
      headerSelector="#top-nav"
      toolsHide
      navigation={
        <SideNavigation
          activeHref={`#/admin/${page}`}
          header={{ href: '#/admin/overview', text: 'Admin' }}
          items={[
            { type: 'link', text: 'Overview', href: '#/admin/overview' },
            {
              type: 'link',
              text: 'Requests',
              href: '#/admin/requests',
              info: reviewCount ? <span>{reviewCount} to review</span> : undefined,
            },
            { type: 'link', text: 'Incidents and alerts', href: '#/admin/incidents' },
            { type: 'link', text: 'Resources and inventory', href: '#/admin/resources' },
            { type: 'link', text: 'Assignments', href: '#/admin/assignments' },
            { type: 'divider' },
            { type: 'link', text: 'How it works', href: '#/admin/how-it-works' },
          ]}
        />
      }
      notifications={<Flashbar items={flashes} />}
      splitPanel={splitPanel?.content}
      splitPanelOpen={Boolean(splitPanel)}
      onSplitPanelToggle={({ detail }) => !detail.open && setSplitPanel(null)}
      splitPanelPreferences={{ position: 'side' }}
      content={<Page setSplitPanel={setSplitPanel} />}
    />
  )
}

export default function App() {
  const page = useHashPage()
  return (
    <DataProvider>
      <TopBar id="top-nav" view={page === 'demo' ? 'demo' : 'admin'} />
      {page === 'demo' ? <DemoPage /> : <Console page={page} />}
    </DataProvider>
  )
}
