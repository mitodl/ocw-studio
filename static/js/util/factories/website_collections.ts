import { WebsiteCollection } from "../../types/website_collections"
import casual from "casual-browserify"
import incrementer from "../incrementer"

const incr = incrementer()

export const makeWebsiteCollection = (): WebsiteCollection => ({
  id:          incr.next().value,
  title:       casual.title,
  description: casual.description
})
