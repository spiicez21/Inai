import { EXCEPTION_LABEL, EXCEPTION_REALITY, fmtPaise } from '@/lib/format'
import type { ExceptionRow } from '@/types/scorecard'
import { AnimatePresence, motion } from 'motion/react'
import { X } from 'lucide-react'
import { Badge, TierBadge } from './primitives'

/**
 * The drill-down. INAI_SPEC.md §11 phase 7: "Judge clicks any record → full chain, no code
 * walkthrough."
 *
 * Phase 0 shows the record and its routing. The decision chain — diagnosis, every scored
 * candidate INCLUDING the rejected ones, the gate verdict, the outcome — slots into the
 * marked section once the recovery core lands. Showing what the agent chose *not* to do is
 * what makes it legible as an agent rather than a workflow.
 */
export function AuditDrawer({
  row,
  onClose,
}: {
  row: ExceptionRow | null
  onClose: () => void
}) {
  return (
    <AnimatePresence>
      {row ? (
        <motion.aside
          key="drawer"
          initial={{ x: '100%' }}
          animate={{ x: 0 }}
          exit={{ x: '100%' }}
          transition={{ type: 'spring', stiffness: 420, damping: 38 }}
          className="fixed inset-y-0 right-0 z-40 flex w-full max-w-md flex-col border-l"
          style={{ background: 'var(--color-card)', borderColor: 'var(--color-border)', boxShadow: 'var(--shadow-pop)' }}
        >
          <header className="flex items-start justify-between gap-3 border-b px-5 py-4"
            style={{ borderColor: 'var(--color-border)' }}>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <TierBadge tier={row.tier} />
                <h2 className="truncate text-sm font-semibold" style={{ color: 'var(--color-fg-strong)' }}>
                  {EXCEPTION_LABEL[row.cls] ?? row.cls}
                </h2>
              </div>
              <p className="num mt-1 text-[0.6875rem]" style={{ color: 'var(--color-fg-subtle)' }}>{row.exception_id}</p>
            </div>
            <button
              onClick={onClose}
              aria-label="Close"
              className="rounded-md p-1 transition-colors hover:bg-[var(--color-inset)]"
              style={{ color: 'var(--color-fg-subtle)' }}
            >
              <X size={16} />
            </button>
          </header>

          <div className="min-h-0 flex-1 overflow-y-auto">
            <Section title="Reality">
              <p className="text-xs leading-relaxed" style={{ color: 'var(--color-fg)' }}>
                {EXCEPTION_REALITY[row.cls] ?? '—'}
              </p>
            </Section>

            <Section title="Amount">
              <p className="num text-2xl font-semibold" style={{ color: 'var(--color-fg-strong)' }}>
                {fmtPaise(row.amount_paise)}
              </p>
            </Section>

            <Section title="The three sides">
              <Field label="Ledger" value={row.ledger_ref} />
              <Field label="Settlement" value={row.settlement_ref} />
              <Field label="Bank" value={row.bank_ref} />
            </Section>

            <Section title="Machine reason">
              <p className="num text-[0.6875rem] leading-relaxed" style={{ color: 'var(--color-fg-muted)' }}>
                {row.machine_reason}
              </p>
            </Section>

            <Section title="Human reason">
              <p className="text-xs leading-relaxed" style={{ color: 'var(--color-fg)' }}>
                {row.human_reason || (
                  <span className="italic" style={{ color: 'var(--color-fg-faint)' }}>
                    Written by the LLM, one line, replay-cached. Not yet generated for this run.
                  </span>
                )}
              </p>
            </Section>

            <Section title="Routed to">
              <Badge tone="accent">{row.routed_action.replaceAll('_', ' ')}</Badge>
            </Section>

            {/* ---- Phase 5+ slots in here -------------------------------- */}
            <Section title="Decision chain">
              <div className="rounded-xl border border-dashed px-3.5 py-4" style={{ borderColor: 'var(--color-border)' }}>
                <p className="text-xs leading-relaxed" style={{ color: 'var(--color-fg-subtle)' }}>
                  Diagnosis, every scored candidate including the rejected ones, the policy-gate
                  verdict with its rule ID and remediation, and the outcome.
                  <br />
                  <span style={{ color: 'var(--color-fg-faint)' }}>Lands with phases 4–5.</span>
                </p>
              </div>
            </Section>
          </div>
        </motion.aside>
      ) : null}
    </AnimatePresence>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-b px-5 py-3.5 last:border-0" style={{ borderColor: 'var(--color-border-soft)' }}>
      <h3 className="eyebrow mb-2">{title}</h3>
      {children}
    </section>
  )
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1">
      <span className="text-[0.6875rem]" style={{ color: 'var(--color-fg-subtle)' }}>{label}</span>
      <span className="num truncate text-[0.6875rem]" style={{ color: 'var(--color-fg)' }}>{value}</span>
    </div>
  )
}
