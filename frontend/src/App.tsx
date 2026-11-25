import { useEffect } from 'react'
import type { MetaResponse } from './api/types'
import { AppShell } from './components/AppShell'
import { ErrorState, LoadingState } from './components/ui/States'
import { setCurrency } from './lib/format'
import { useApi } from './lib/hooks'
import { useRoute } from './lib/router'
import { AnalystPage } from './pages/AnalystPage'
import { BridgePage } from './pages/BridgePage'
import { DataQualityPage } from './pages/DataQualityPage'
import { OnboardingPage } from './pages/OnboardingPage'
import { OverviewPage } from './pages/OverviewPage'
import { PricingPage } from './pages/PricingPage'
import { ReferralsPage } from './pages/ReferralsPage'
import { RetentionPage } from './pages/RetentionPage'

const PAGES: Record<string, () => React.JSX.Element> = {
  overview: OverviewPage,
  bridge: BridgePage,
  onboarding: OnboardingPage,
  pricing: PricingPage,
  referrals: ReferralsPage,
  retention: RetentionPage,
  'data-quality': DataQualityPage,
}

export default function App() {
  const route = useRoute()
  const meta = useApi<MetaResponse>('/api/meta')
  const currency = meta.data?.meta.currency

  useEffect(() => setCurrency(currency), [currency])
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [route.page])

  const Page = PAGES[route.page]
  let body: React.ReactNode
  if (!meta.data && meta.loading) body = <LoadingState />
  else if (!meta.data && meta.error) body = <ErrorState error={meta.error} onRetry={meta.reload} />
  else if (route.page === 'analyst') body = <AnalystPage initialQuestion={route.params.get('q')} status={meta.data!.analyst} />
  else if (Page) body = <Page key={route.page} />
  else body = <OverviewPage />

  return (
    <AppShell page={route.page} meta={meta.data?.meta ?? null} analyst={meta.data?.analyst ?? null}>
      {body}
    </AppShell>
  )
}
