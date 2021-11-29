import {
  WebsiteCollection,
  WebsiteCollectionItem
} from "../../types/website_collections"
import casual from "casual"
import incrementer from "../incrementer"

const incr = incrementer()

export const makeWebsiteCollection = (): WebsiteCollection => ({
  id:          incr.next().value,
  title:       casual.title,
  description: casual.description
})

const positionIncr = incrementer()

export const makeWebsiteCollectionItem = (
  collection?: WebsiteCollection
): WebsiteCollectionItem => ({
  position:           positionIncr.next().value,
  id:                 incr.next().value,
  website:            casual.uuid,
  website_collection: collection ? collection.id : casual.integer(1),
  website_title:      casual.title
})
