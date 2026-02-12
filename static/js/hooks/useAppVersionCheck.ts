import { useEffect, useRef } from "react"
import { useLocation } from "react-router-dom"

const HASH_URL = "/static/hash.txt"

async function fetchHash(): Promise<string | null> {
  try {
    const response = await fetch(HASH_URL, { cache: "no-store" })
    if (!response.ok) return null
    const text = await response.text()
    return text.trim()
  } catch {
    return null
  }
}

/**
 * Checks the deployed app version (via /static/hash.txt) on every
 * pathname change. If the hash has changed since initial page load,
 * forces a full page reload so users always get the latest bundle.
 *
 * Intentionally scoped to pathname changes only — query param changes
 * (e.g. ?publish=, pagination, search) are transient UI state and
 * should not trigger a reload mid-action.
 */
export default function useAppVersionCheck(): void {
  const hashRef = useRef<string | null>(null)
  const location = useLocation()

  useEffect(() => {
    let active = true
    fetchHash().then((hash) => {
      if (!active || !hash) return

      if (!hashRef.current) {
        hashRef.current = hash
      } else if (hash !== hashRef.current) {
        window.location.reload()
      }
    })

    return () => {
      active = false
    }
  }, [location.pathname])
}
