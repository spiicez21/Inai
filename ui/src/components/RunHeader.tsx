import { fmtCount, fmtDuration, fmtThroughput } from '@/lib/format'
import type { RunMeta } from '@/types/scorecard'
import { Check, Copy } from 'lucide-react'
import { useState } from 'react'
import { Badge } from './primitives'

/**
 * Seed and config hash, on the face of the scorecard. INAI_SPEC.md §12 step 8:
 * "re-run it yourself." The closing slide needs something to point at, and this is it —
 * the hash is copyable so a judge can actually do it.
 */
export function RunHeader({ meta }: { meta: RunMeta }) {
  const [copied, setCopied] = useState(false)
  const command = `uv run inai run --config configs/${meta.config_name}.yaml --seed ${meta.seed}`

  async function copy() {
    await navigator.clipboard.writeText(command)
    setCopied(true)
    setTimeout(() => setCopied(false), 1600)
  }

  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1
          className="text-[1.375rem] leading-tight font-semibold tracking-tight"
          style={{ color: 'var(--color-fg-strong)' }}
        >
          Scorecard
        </h1>
        <p className="mt-1 text-xs" style={{ color: 'var(--color-fg-subtle)' }}>
          Match first. Then chase. · {fmtCount(meta.n_records)} records ·{' '}
          {fmtDuration(meta.duration_seconds)}
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="neutral">config {meta.config_name}</Badge>
        <Badge tone="neutral">seed {meta.seed}</Badge>
        <Badge tone="lime" title={meta.hardware}>
          {fmtThroughput(meta.records_per_second)}
        </Badge>
        <Badge tone={meta.llm_mode === 'replay' ? 'accent' : 'exception'}>
          llm {meta.llm_mode}
        </Badge>
        <button
          onClick={copy}
          title={`Copy: ${command}`}
          className="flex items-center gap-1.5 rounded-lg px-2 py-1 text-[0.6875rem] font-medium transition-colors"
          style={{ background: 'var(--color-inset)', color: 'var(--color-fg-muted)' }}
        >
          <span className="num">{meta.config_hash.slice(0, 12)}</span>
          {copied ? (
            <Check size={11} style={{ color: 'var(--color-matched)' }} />
          ) : (
            <Copy size={11} className="opacity-60" />
          )}
        </button>
      </div>
    </div>
  )
}
