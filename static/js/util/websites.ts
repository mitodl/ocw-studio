import { WebsiteContentListItem } from "../types/websites"
import { DateTime } from "luxon"

/**
 * Returns a string representation of when this item was last updated, relative
 * to today. For example, "2 days ago"
 */
export const formatUpdatedOn = (wc: WebsiteContentListItem): string => {
  const relative = DateTime.fromISO(wc.updated_on).toRelative()
  if (relative === null) {
    /**
     * luxon will only return null if the date was invalid.
     */
    throw new Error("Invalid date.")
  }
  return relative
}
