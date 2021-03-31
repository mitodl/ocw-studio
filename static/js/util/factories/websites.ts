import casual from "casual-browserify"
import { times, cloneDeep } from "lodash"

import incrementer from "../incrementer"
import {
  exampleSiteConfig,
  ROLE_ADMIN,
  ROLE_EDITOR,
  ROLE_GLOBAL,
  ROLE_OWNER,
  WEBSITES_PAGE_SIZE
} from "../../constants"

import {
  ConfigItem,
  ConfigField,
  WidgetVariant,
  Website,
  WebsiteCollaborator,
  WebsiteContent,
  WebsiteContentListItem,
  WebsiteStarter,
  WebsiteStarterConfig
} from "../../types/websites"

const incr = incrementer()

export const makeWebsiteConfigField = (
  props: Record<string, any> = {}
): ConfigField => {
  const label = props.label ?? casual.word

  return {
    label,
    name:   label.toLowerCase(),
    widget: props.widget,
    ...props
  }
}

export const makeWebsiteConfigItem = (name: string): ConfigItem => ({
  fields: [
    {
      label:  "Title",
      name:   "title",
      widget: WidgetVariant.String
    },
    {
      label:  "Content",
      name:   "content",
      widget: WidgetVariant.Markdown
    }
  ],
  folder:   casual.word,
  label:    casual.word,
  name:     name || casual.word,
  category: casual.word
})

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
  metadata: {
    course_numbers: [`${casual.integer(1, 20)}.${casual.integer(1, 999)}`],
    term:           `${casual.month_name} ${casual.year}`
  }
})

export const makeWebsiteListing = (): Website[] =>
  times(WEBSITES_PAGE_SIZE).map(() => makeWebsiteDetail())

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
  type:  casual.word
})

export const makeWebsiteContentDetail = (): WebsiteContent => ({
  ...makeWebsiteContentListItem(),
  markdown: casual.text,
  metadata: {
    description: casual.short_description
  }
})
