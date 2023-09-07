import { useEffect } from "react"

interface Props {
  title: string
}

const TITLE_BASE = "OCW Studio"

/**
 * Format page titles for OCW Studio.
 *
 * This function takes any number of 'subtitles' and then joins
 * them up to `TITLE_BASE` (`"OCW Studio"`) with pipe characters as
 * a separator.
 *
 * So `formatTitle("My Site Page")` will be `"OCW Studio | My Site Page"`.
 */
export const formatTitle = (...subtitles: string[]): string =>
  [TITLE_BASE]
    .concat(subtitles.flatMap((subtitle) => ["|", subtitle.trim()]))
    .join(" ")

/**
 * Takes a title string prop and sets it as the document title
 * when it mounts.
 *
 * Take care not to have more than one of these mounted at the same
 * time, as you'll probably have a race condition where whichever
 * one mounts second 'wins' and sets the title, overriding the other.
 */
export default function DocumentTitle(props: Props): null {
  const { title } = props

  useEffect(() => {
    document.title = title
  }, [title])

  return null
}
