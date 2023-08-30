import { PublishStatus } from "../constants"
import { Website } from "../types/websites"

/**
 * Get the most recent publish status for a website
 */
export const latestPublishStatus = (website: Website): PublishStatus | null =>
  website
    ? (website.draft_publish_status_updated_on ?? "") <
      (website.live_publish_status_updated_on ?? "")
      ? website.live_publish_status
      : website.draft_publish_status
    : null
