import casual from "casual-browserify"
import { times } from "lodash"

import incrementer from "../incrementer"

import {
  Website,
  WebsiteStarter,
  WebsiteStarterConfig
} from "../../types/websites"

const incr = incrementer()

export const makeWebsiteStarterConfig = (): WebsiteStarterConfig => ({
  collections: [
    {
      name:   "page",
      label:  "Page",
      fields: [
        {
          name:   "title",
          label:  "Title",
          widget: "string"
        },
        {
          name:   "content",
          label:  "Content",
          widget: "markdown"
        }
      ]
    },
    {
      name:   "resource",
      label:  "Resource",
      fields: [
        {
          name:   "title",
          label:  "Title",
          widget: "string"
        },
        {
          name:   "description",
          label:  "Description",
          widget: "markdown"
        }
      ]
    }
  ]
})

export const makeWebsiteStarter = (type = "course"): WebsiteStarter => ({
  id:     incr.next().value,
  name:   casual.title,
  path:   casual.url,
  source: casual.word,
  commit: null,
  slug:   type,
  config: makeWebsiteStarterConfig()
})

export const makeWebsite = (): Website => ({
  uuid:       casual.uuid,
  created_on: casual.moment.format(),
  updated_on: casual.moment.format(),
  name:       times(5)
    .map(() => casual.word)
    .join("-"),
  title:    casual.title,
  source:   null,
  starter:  makeWebsiteStarter("course"),
  metadata: null
})

export const makeWebsites = (): Website[] => times(5).map(() => makeWebsite())
