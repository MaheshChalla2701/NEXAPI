import { useEffect, useRef, useState, type FormEvent } from 'react'
import { ApiError, api } from '../api/client'
import type { AnalystAnswer, AnalystStatus, Suggestion } from '../api/types'
import { Icon } from '../components/ui/Icon'
import { PageHeader, Segmented } from '../components/ui/Layout'

const MAX_CHARS = 500
type Mode = 'auto' | 'local' | 'external'

interface Turn {
  id: number
  question: string
  answer?: AnalystAnswer
  error?: string
}

export function AnalystPage({ initialQuestion, status }: { initialQuestion: string | null; status: AnalystStatus }) {
  const [turns, setTurns] = useState<Turn[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [mode, setMode] = useState<Mode>('auto')
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const asked = useRef<string | null>(null)
  const nextId = useRef(1)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.suggestions().then((r) => setSuggestions(r.suggestions)).catch(() => setSuggestions([]))
  }, [])

  const ask = async (question: string) => {
    const q = question.trim()
    if (!q || busy) return
    const id = nextId.current++
    setTurns((t) => [...t, { id, question: q }])
    setInput('')
    setBusy(true)
    try {
      const answer = await api.ask(q, mode)
      setTurns((t) => t.map((x) => (x.id === id ? { ...x, answer } : x)))
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : 'Something went wrong.'
      setTurns((t) => t.map((x) => (x.id === id ? { ...x, error: msg } : x)))
    } finally {
      setBusy(false)
    }
  }

  // Questions linked from charts (#/analyst?q=...) are asked once on arrival.
  useEffect(() => {
    if (initialQuestion && asked.current !== initialQuestion) {
      asked.current = initialQuestion
      void ask(initialQuestion)
    }
  }, [initialQuestion])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [turns])

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    void ask(input)
  }

  const externalReady = status.external_configured
  const activeMode = mode === 'local' || !externalReady ? 'local' : 'external'

  return (
    <div className="analyst">
      <PageHeader
        eyebrow="Assistant"
        title="AI Analyst"
        description="Ask about the revenue change, the initiatives or the data. Every number in an answer comes from the analysis database."
        actions={
          <div className="analyst-mode">
            <span className={`mode-pill ${activeMode}`}>
              <span className={`mode-dot ${activeMode === 'external' ? 'ext' : ''}`} />
              {activeMode === 'external' ? `External AI · ${status.external_model}` : 'Local engine · rule-based'}
            </span>
            <Segmented<Mode>
              label="Answer mode"
              value={mode}
              onChange={setMode}
              options={[
                { value: 'auto', label: 'Auto' },
                { value: 'local', label: 'Local only' },
              ]}
            />
          </div>
        }
      />

      {!externalReady && (
        <p className="analyst-disclaimer">
          <Icon name="info" size={15} />
          Running the local engine: it matches your question to a fixed set of analyses and answers from the database. It
          is not a language model and will say so when a question is outside what it can answer. External AI is off by
          default; see the README to enable it.
        </p>
      )}

      <div className="thread" aria-live="polite">
        {turns.length === 0 && (
          <div className="thread-empty">
            <span className="analyst-emblem"><Icon name="sparkle" size={30} /></span>
            <h3>Make sense of the bigger picture.</h3>
            <p className="analyst-intro">Pick a starting point, or ask a question of your own.</p>
            <div className="chips">
              {suggestions.map((s) => (
                <button key={s.question} type="button" className="chip" onClick={() => void ask(s.question)}>
                  {s.question}
                </button>
              ))}
            </div>
          </div>
        )}
        {turns.map((t) => (
          <div key={t.id} className="turn">
            <div className="bubble-q">{t.question}</div>
            {t.error ? (
              <div className="answer answer-error" role="alert">
                <Icon name="alert" size={16} /> {t.error}
              </div>
            ) : t.answer ? (
              <AnswerCard a={t.answer} onAsk={(q) => void ask(q)} />
            ) : (
              <div className="answer answer-pending">
                <span className="typing" aria-label="Thinking">
                  <span />
                  <span />
                  <span />
                </span>
              </div>
            )}
          </div>
        ))}
        <div ref={endRef} />
      </div>

      <form className="composer" onSubmit={onSubmit}>
        <label htmlFor="q" className="sr-only">
          Your question
        </label>
        <textarea
          id="q"
          rows={1}
          value={input}
          maxLength={MAX_CHARS}
          placeholder="Ask about revenue drivers, an initiative, retention or data quality…"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              void ask(input)
            }
          }}
        />
        <span className="char-count">
          {input.length}/{MAX_CHARS}
        </span>
        <button type="submit" className="btn btn-primary" disabled={busy || !input.trim()}>
          <Icon name="send" size={15} /> Ask
        </button>
      </form>
    </div>
  )
}

function AnswerCard({ a, onAsk }: { a: AnalystAnswer; onAsk: (q: string) => void }) {
  return (
    <article className={`answer ${a.answered ? '' : 'answer-unanswered'}`}>
      <header className="answer-head">
        <h3>{a.title}</h3>
        <span className={`mode-pill small ${a.mode}`}>
          <span className={`mode-dot ${a.mode === 'external' ? 'ext' : ''}`} />
          {a.mode === 'external' ? `External · ${a.model}` : 'Local engine'}
        </span>
      </header>
      {a.notices.map((n) => (
        <p key={n} className="answer-notice">
          <Icon name="alert" size={14} /> {n}
        </p>
      ))}
      <div className="answer-body">
        {a.summary.map((p, i) => (
          <p key={i}>{p}</p>
        ))}
      </div>
      {a.evidence.length > 0 && (
        <details className="answer-section" open={a.evidence.length <= 4}>
          <summary>Evidence ({a.evidence.length})</summary>
          <table className="evidence">
            <tbody>
              {a.evidence.map((e) => (
                <tr key={e.label + e.source}>
                  <td>{e.label}</td>
                  <td className="num">
                    <strong>{e.value}</strong>
                  </td>
                  <td>
                    <code>{e.source}</code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
      {a.answered && (
        <dl className="answer-meta">
          <div>
            <dt>Confidence</dt>
            <dd>{a.confidence}</dd>
          </div>
        </dl>
      )}
      {a.limitations.length > 0 && (
        <div className="answer-section">
          <div className="eyebrow">Limitations</div>
          <ul>
            {a.limitations.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </div>
      )}
      {a.next_actions.length > 0 && (
        <div className="answer-section">
          <div className="eyebrow">Suggested next steps</div>
          <ul>
            {a.next_actions.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </div>
      )}
      {a.related.length > 0 && (
        <div className="chips">
          {a.related.map((r) => (
            <button key={r} type="button" className="chip" onClick={() => onAsk(r)}>
              {r}
            </button>
          ))}
        </div>
      )}
    </article>
  )
}
