import { cn } from '@/lib/cn'
import type { Theme } from '@/lib/theme'
import {
  BookOpen,
  LayoutDashboard,
  ListTree,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  ShieldCheck,
  Split,
  Sun,
  Layers,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

export interface NavItem {
  id: string
  label: string
  icon: LucideIcon
  /** Shown as a count chip. Present only where a number means something. */
  badge?: number
}

export const NAV: NavItem[] = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'bridge', label: 'The bridge', icon: Split },
  { id: 'tiers', label: 'Match tiers', icon: Layers },
  { id: 'arms', label: 'Arms & CI', icon: ListTree },
  { id: 'exceptions', label: 'Exceptions', icon: BookOpen },
  { id: 'policy', label: 'Policy blocks', icon: ShieldCheck },
]

export function Sidebar({
  active,
  onNavigate,
  counts,
  collapsed,
  onToggleCollapse,
  theme,
  onToggleTheme,
}: {
  active: string
  onNavigate: (id: string) => void
  counts: Record<string, number | undefined>
  collapsed: boolean
  onToggleCollapse: () => void
  theme: Theme
  onToggleTheme: () => void
}) {
  return (
    <aside
      className={cn(
        'card sticky top-4 flex h-[calc(100dvh-2rem)] flex-col transition-[width] duration-200',
        collapsed ? 'w-[4.5rem]' : 'w-60',
      )}
    >
      {/* Collapsed, the header stacks: a 32px mark plus a toggle plus their gaps does not
          fit 72px side by side, which is what made this look wedged. */}
      <div
        className={cn(
          'pt-5 pb-4',
          collapsed ? 'flex flex-col items-center gap-3 px-2' : 'flex items-center gap-2.5 px-4',
        )}
      >
        <span
          className="grid size-8 shrink-0 place-items-center rounded-[0.6rem]"
          style={{ background: 'var(--color-lime)' }}
          aria-hidden
        >
          <svg viewBox="0 0 24 24" className="size-4" fill="none">
            <path
              d="M6 5h12M6 11h9M6 17h5"
              stroke="var(--color-accent-strong)"
              strokeWidth="2.6"
              strokeLinecap="round"
            />
          </svg>
        </span>
        {!collapsed && (
          <>
            <span
              className="text-[1.0625rem] font-semibold tracking-tight"
              style={{ color: 'var(--color-fg-strong)' }}
            >
              INAI
            </span>
            <span className="text-sm" style={{ color: 'var(--color-fg-faint)' }}>
              இணை
            </span>
          </>
        )}
        <button
          onClick={onToggleCollapse}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className={cn(
            'rounded-md p-1.5 transition-colors hover:bg-[var(--color-inset)]',
            collapsed ? '' : 'ml-auto',
          )}
          style={{ color: 'var(--color-fg-subtle)' }}
        >
          {collapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
        </button>
      </div>

      {!collapsed && (
        <p className="eyebrow px-4 pb-2" style={{ color: 'var(--color-fg-faint)' }}>
          Scorecard
        </p>
      )}

      <nav className={cn('flex flex-col gap-1', collapsed ? 'px-2' : 'px-2.5')}>
        {NAV.map((item) => {
          const Icon = item.icon
          const on = active === item.id
          const badge = counts[item.id]
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              title={
                collapsed
                  ? badge !== undefined
                    ? `${item.label} — ${badge}`
                    : item.label
                  : undefined
              }
              className={cn(
                'relative flex items-center rounded-[0.7rem] text-[0.8125rem] transition-colors',
                collapsed ? 'h-10 justify-center' : 'gap-2.5 px-2.5 py-2',
                on ? 'font-medium' : 'hover:bg-[var(--color-inset)]',
              )}
              style={
                on
                  ? { background: 'var(--color-inset)', color: 'var(--color-fg-strong)' }
                  : { color: 'var(--color-fg-muted)' }
              }
            >
              <Icon size={16} className="shrink-0" style={on ? { color: 'var(--color-accent)' } : undefined} />
              {collapsed ? (
                // The count has nowhere to go at 72px, but dropping it entirely loses the
                // signal that this section has contents. A dot keeps the signal; the exact
                // number is in the tooltip and one click away.
                badge !== undefined && badge > 0 ? (
                  <span
                    aria-hidden
                    className="absolute top-1.5 right-1.5 size-1.5 rounded-full"
                    style={{ background: 'var(--color-accent)' }}
                  />
                ) : null
              ) : (
                <>
                  <span className="truncate">{item.label}</span>
                  {badge !== undefined && (
                    <span
                      className="num ml-auto rounded-md px-1.5 py-0.5 text-[0.625rem]"
                      style={{ background: 'var(--color-card-2)', color: 'var(--color-fg-subtle)' }}
                    >
                      {badge > 999 ? `${(badge / 1000).toFixed(1)}k` : badge}
                    </span>
                  )}
                </>
              )}
            </button>
          )
        })}
      </nav>

      <div className={cn('mt-auto pb-4', collapsed ? 'px-2' : 'px-2.5')}>
        {!collapsed && (
          <p className="eyebrow px-2.5 pb-2" style={{ color: 'var(--color-fg-faint)' }}>
            Appearance
          </p>
        )}
        <button
          onClick={onToggleTheme}
          className={cn(
            'flex w-full items-center rounded-[0.7rem] text-[0.8125rem] transition-colors hover:bg-[var(--color-inset)]',
            collapsed ? 'h-10 justify-center' : 'gap-2.5 px-2.5 py-2',
          )}
          style={{ color: 'var(--color-fg-muted)' }}
          title={collapsed ? (theme === 'dark' ? 'Light mode' : 'Dark mode') : undefined}
        >
          {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
          {!collapsed && <span>{theme === 'dark' ? 'Light mode' : 'Dark mode'}</span>}
        </button>
      </div>
    </aside>
  )
}
