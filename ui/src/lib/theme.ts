import { useCallback, useEffect, useState } from 'react'

export type Theme = 'light' | 'dark'

const KEY = 'inai-theme'

function systemTheme(): Theme {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function stored(): Theme | null {
  try {
    const v = localStorage.getItem(KEY)
    return v === 'light' || v === 'dark' ? v : null
  } catch {
    // Private windows and blocked site-data throw on access rather than returning null.
    return null
  }
}

function apply(theme: Theme) {
  document.documentElement.dataset.theme = theme
}

// Applied at module load, before React's first render. Two reasons:
//   * no flash of the wrong theme;
//   * chart colours are read from the tokens DURING render (SVG marks take literal
//     colours), so the attribute must already be correct by then.
if (typeof document !== 'undefined') {
  apply(stored() ?? systemTheme())
}

/**
 * Theme state. Explicit choice wins and persists; otherwise the OS preference is followed
 * live, so a system change mid-demo is picked up without a reload.
 */
export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(() => stored() ?? systemTheme())
  const [isExplicit, setIsExplicit] = useState(() => stored() !== null)

  useEffect(() => {
    if (isExplicit) return
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => {
      const next = systemTheme()
      apply(next)
      setThemeState(next)
    }
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [isExplicit])

  const setTheme = useCallback((next: Theme) => {
    // Applied synchronously, BEFORE the state update schedules a re-render — charts read
    // the tokens during that render, so an effect would be one paint too late.
    apply(next)
    setThemeState(next)
    setIsExplicit(true)
    try {
      localStorage.setItem(KEY, next)
    } catch {
      // Non-fatal: the theme still applies for this session.
    }
  }, [])

  const toggle = useCallback(
    () => setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'),
    [setTheme],
  )

  return { theme, setTheme, toggle }
}

/**
 * Read a design token as a concrete colour string.
 *
 * Observable Plot renders to SVG imperatively and cannot use CSS custom properties for
 * mark fills, so chart colours are resolved from the same tokens at render time. Keying the
 * chart's memo on `theme` is what makes charts follow the toggle.
 */
export function token(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(`--color-${name}`).trim()
}
