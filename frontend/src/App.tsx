import { Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { SearchPage } from './pages/SearchPage'
import { JobsPage } from './pages/JobsPage'
import { FiltersPage } from './pages/FiltersPage'
import { SettingsPage } from './pages/SettingsPage'
import { LearnFinderPage } from './pages/LearnFinderPage'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<SearchPage />} />
        <Route path="/jobs" element={<JobsPage />} />
        <Route path="/saved" element={<FiltersPage />} />
        <Route path="/learn" element={<LearnFinderPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>
    </Layout>
  )
}

export default App
