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
 * route change. If the hash has changed since initial page load,
 * forces a full page reload so users always get the latest bundle.
 */
export default function useAppVersionCheck(): void {
  const initialHash = useRef<string | null>(null)
  const hasFetched = useRef(false)
  const location = useLocation()

  useEffect(() => {
    fetchHash().then((hash) => {
      if (hash) {
        initialHash.current = hash
      }
      hasFetched.current = true
    })
  }, [])

  useEffect(() => {
    if (!hasFetched.current) return

    let active = true
    fetchHash().then((hash) => {
      if (!active || !hash) return

      if (!initialHash.current) {
        initialHash.current = hash
        return
      }

      if (hash !== initialHash.current) {
        window.location.reload()
      }
    })

    return () => {
      active = false
    }
  }, [location.pathname])
}
