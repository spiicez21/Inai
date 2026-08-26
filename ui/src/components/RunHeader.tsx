import { fmtCount, fmtDuration, fmtThroughput } from '@/lib/format'
import type { RunMeta } from '@/types/scorecard'
import { Copy, Check } from 'lucide-react'
import { useState } from 'react'

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
    <header className="border-base-800 bg-base-950/85 sticky top-0 z-30 border-b backdrop-blur">
      <div className="mx-auto flex max-w-[110rem] flex-wrap items-center gap-x-6 gap-y-2 px-5 py-3">
        <div className="flex items-baseline gap-2.5">
          <span className="text-base-50 text-base font-semibold tracking-tight">INAI</span>
          <span className="text-base-600 text-sm">இணை</span>
          <span className="text-base-500 hidden text-xs sm:inline">Match first. Then chase.</span>
        </div>

        <div className="ml-auto flex flex-wrap items-center gap-x-5 gap-y-1 text-[0.6875rem]">
          <Meta label="config" value={meta.config_name} />
          <Meta label="seed" value={String(meta.seed)} />
          <Meta label="records" value={fmtCount(meta.n_records)} />
          <Meta
            label="throughput"
            value={fmtThroughput(meta.records_per_second)}
            title={`${fmtDuration(meta.duration_seconds)} on ${meta.hardware}`}
          />
          <Meta label="llm" value={meta.llm_mode} />
          <button
            onClick={copy}
            title={`Copy: ${command}`}
            className="text-base-500 hover:text-base-200 hover:bg-base-850 group flex items-center gap-1.5 rounded px-1.5 py-1"
          >
            <span className="text-base-600">config_hash</span>
            <span className="num text-base-300">{meta.config_hash.slice(0, 12)}</span>
            {copied ? (
              <Check size={11} className="text-matched" />
            ) : (
              <Copy size={11} className="opacity-50 group-hover:opacity-100" />
            )}
          </button>
        </div>
      </div>
    </header>
  )
}

function Meta({ label, value, title }: { label: string; value: string; title?: string }) {
  return (
    <span className="flex items-center gap-1.5" title={title}>
      <span className="text-base-600">{label}</span>
      <span className="num text-base-300">{value}</span>
    </span>
  )
}
