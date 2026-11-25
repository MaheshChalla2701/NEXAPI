import type { Initiative } from '../api/types'
import { ConfidenceBadge, RecommendationBadge } from './ui/Badges'
import { Card } from './ui/Layout'

/** Recommendation block shared by the three initiative pages. */
export function InitiativeHeader({ initiative, isMock }: { initiative: Initiative; isMock: boolean }) {
  const pending = initiative.recommendation === 'PENDING'
  return (
    <Card className="initiative-card">
      <div className="initiative-top">
        <div>
          <div className="eyebrow">Recommendation</div>
          <div className="initiative-verdict">
            <RecommendationBadge value={initiative.recommendation} />
            {!pending && <ConfidenceBadge value={initiative.confidence} isMock={isMock} />}
          </div>
        </div>
        <dl className="facts">
          <div>
            <dt>Launched</dt>
            <dd>{initiative.launched}</dd>
          </div>
          <div>
            <dt>Scope</dt>
            <dd>{initiative.scope}</dd>
          </div>
        </dl>
      </div>
      <p className="initiative-headline">{initiative.headline}</p>
      <p className="muted">{initiative.rationale}</p>
      {initiative.monitoring.length > 0 && (
        <div className="monitoring">
          <div className="eyebrow">What to watch next</div>
          <ul>
            {initiative.monitoring.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  )
}
