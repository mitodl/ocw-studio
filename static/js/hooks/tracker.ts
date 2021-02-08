import { useEffect } from "react"
import { useLocation } from "react-router-dom"
import ga from "react-ga"

/**
 * A hook providing google analytics pageviews through
 * react-ga. It listens for react-router pageview changes,
 * so it will correctly record page navigation in a SPA.
 */
export default function useTracker(): void {
  useEffect(() => {
    const debug = SETTINGS.reactGaDebug === "true"

    if (SETTINGS.gaTrackingID) {
      ga.initialize(SETTINGS.gaTrackingID, { debug: debug })
    }
  }, [])

  const location = useLocation()

  useEffect(() => {
    const page = location.pathname

    if (SETTINGS.gaTrackingID) {
      ga.pageview(page)
    }
  }, [location])
}
