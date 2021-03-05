import casual from "casual-browserify"
import { times, cloneDeep } from "lodash"

import incrementer from "../incrementer"
import {
  exampleSiteConfig,
  ROLE_ADMIN,
  ROLE_EDITOR,
  ROLE_GLOBAL,
  ROLE_OWNER
} from "../../constants"

import {
  Website,
  WebsiteCollaborator,
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

export const makeWebsiteDetail = (): Website => ({
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

export const makeWebsiteDetails = (): Website[] =>
  times(5).map(() => makeWebsiteDetail())

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
