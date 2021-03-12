import casual from "casual-browserify"
import { times, cloneDeep } from "lodash"

import incrementer from "../incrementer"
import {
  CONTENT_TYPES,
  exampleSiteConfig,
  ROLE_ADMIN,
  ROLE_EDITOR,
  ROLE_GLOBAL,
  ROLE_OWNER,
  WEBSITES_PAGE_SIZE
} from "../../constants"

import {
  Website,
  WebsiteCollaborator,
  WebsiteContent,
  WebsiteContentListItem,
  WebsiteStarter,
  WebsiteStarterConfig
} from "../../types/websites"

const incr = incrementer()

export const makeWebsiteStarterConfig = (): WebsiteStarterConfig =>
  cloneDeep(exampleSiteConfig)

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
  metadata: {
    course_numbers: [`${casual.integer(1, 20)}.${casual.integer(1, 999)}`],
    term:           `${casual.month_name} ${casual.year}`
  }
})

export const makeWebsiteListing = (): Website[] =>
  times(WEBSITES_PAGE_SIZE).map(() => makeWebsite())

export const makeWebsiteCollaborator = (): WebsiteCollaborator => ({
  name:     casual.name,
  username: casual.word,
  email:    casual.email,
  role:     casual.random_element([ROLE_ADMIN, ROLE_EDITOR]),
  group:    casual.word
})

export const makePermanentWebsiteCollaborator = (): WebsiteCollaborator => ({
  name:     casual.name,
  username: casual.word,
  email:    casual.email,
  role:     casual.random_element([ROLE_GLOBAL, ROLE_OWNER]),
  group:    casual.word
})

export const makeWebsiteCollaborators = (): WebsiteCollaborator[] =>
  times(5).map(() => makeWebsiteCollaborator())

export const makeWebsiteContentListItem = (): WebsiteContentListItem => ({
  uuid:  casual.uuid,
  title: casual.title,
  type:  casual.random_element(CONTENT_TYPES)
})

export const makeWebsiteContentDetail = (): WebsiteContent => ({
  ...makeWebsiteContentListItem(),
  markdown: casual.text,
  metadata: {
    description: casual.short_description
  }
})
