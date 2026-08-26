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
          className="border-base-800 bg-base-925 fixed inset-y-0 right-0 z-40 flex w-full max-w-md flex-col border-l shadow-2xl"
        >
          <header className="border-base-800 flex items-start justify-between gap-3 border-b px-4 py-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <TierBadge tier={row.tier} />
                <h2 className="text-base-100 truncate text-sm font-medium">
                  {EXCEPTION_LABEL[row.cls] ?? row.cls}
                </h2>
              </div>
              <p className="num text-base-500 mt-1 text-[0.6875rem]">{row.exception_id}</p>
            </div>
            <button
              onClick={onClose}
              aria-label="Close"
              className="text-base-500 hover:text-base-200 hover:bg-base-850 rounded p-1"
            >
              <X size={16} />
            </button>
          </header>

          <div className="min-h-0 flex-1 overflow-y-auto">
            <Section title="Reality">
              <p className="text-base-300 text-xs leading-relaxed">
                {EXCEPTION_REALITY[row.cls] ?? '—'}
              </p>
            </Section>

            <Section title="Amount">
              <p className="num text-base-50 text-xl font-semibold">{fmtPaise(row.amount_paise)}</p>
            </Section>

            <Section title="The three sides">
              <Field label="Ledger" value={row.ledger_ref} />
              <Field label="Settlement" value={row.settlement_ref} />
              <Field label="Bank" value={row.bank_ref} />
            </Section>

            <Section title="Machine reason">
              <p className="num text-base-300 text-[0.6875rem] leading-relaxed">
                {row.machine_reason}
              </p>
            </Section>

            <Section title="Human reason">
              <p className="text-base-300 text-xs leading-relaxed">
                {row.human_reason || (
                  <span className="text-base-600 italic">
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
              <div className="border-base-800 rounded border border-dashed px-3 py-4">
                <p className="text-base-600 text-xs leading-relaxed">
                  Diagnosis, every scored candidate including the rejected ones, the policy-gate
                  verdict with its rule ID and remediation, and the outcome.
                  <br />
                  <span className="text-base-700">Lands with phases 4–5.</span>
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
    <section className="border-base-850 border-b px-4 py-3 last:border-0">
      <h3 className="eyebrow mb-2">{title}</h3>
      {children}
    </section>
  )
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1">
      <span className="text-base-500 text-[0.6875rem]">{label}</span>
      <span className="num text-base-200 truncate text-[0.6875rem]">{value}</span>
    </div>
  )
}
