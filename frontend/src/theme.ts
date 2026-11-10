import { useState } from 'react'

export type Theme = 'light' | 'dark'
const KEY = 'theme'

/** Light or dark. index.html picks the start (the saved choice, else the system's) before the
 * first paint; the button flips it and saves the choice when the browser allows. */
export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() => (document.documentElement.classList.contains('dark') ? 'dark' : 'light'))
  const toggle = () => {
    const next = theme === 'dark' ? 'light' : 'dark'
    document.documentElement.classList.toggle('dark', next === 'dark')
    try {
      localStorage.setItem(KEY, next)
    } catch {
      // not remembered, still applied
    }
    setTheme(next)
  }
  return [theme, toggle]
}
