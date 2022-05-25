import casual from "casual"
import { cloneDeep, times } from "lodash"

import incrementer from "../incrementer"
import {
  ROLE_ADMIN,
  ROLE_EDITOR,
  ROLE_GLOBAL,
  ROLE_OWNER,
  WEBSITES_PAGE_SIZE,
  WebsiteStarterStatus
} from "../../constants"
import exampleSiteConfig from "../../resources/ocw-course-site-config.json"

import {
  ConfigField,
  WidgetVariant,
  EditableConfigItem,
  SingletonConfigItem,
  SingletonsConfigItem,
  RepeatableConfigItem,
  TopLevelConfigItem,
  Website,
  WebsiteCollaborator,
  WebsiteContent,
  WebsiteContentListItem,
  WebsiteStarter,
  WebsiteStarterConfig,
  WebsiteStatus
} from "../../types/websites"
import { WebsiteListingResponse } from "../../query-configs/websites"

const incr = incrementer()

/**
 * Factory for ConfigField, useful for testing various functions that switch
 * on field.widget
 *
 * A ConfigField for a specific widget can be created by passing a prop object
 * with the `widget` key set:
 *
 * ```ts
 * const myConfigField = makeWebsiteConfigField({ widget: WidgetVariant.Select })
 * ```
 **/
export const makeWebsiteConfigField = (
  props: Record<string, any> = {}
): ConfigField => {
  const label = props.label ?? casual.word

  if (props.widget && props.widget === WidgetVariant.Object && !props.fields) {
    props.fields = [
      makeWebsiteConfigField({
        widget: WidgetVariant.String,
        label:  "mystring"
      }),
      makeWebsiteConfigField({
        widget:   WidgetVariant.Select,
        multiple: true,
        label:    "myselect"
      })
    ]
  }

  return {
    label,
    name:   label.toLowerCase(),
    widget: props.widget ?? WidgetVariant.String,
    ...props
  }
}

const exampleFields: ConfigField[] = [
  {
    label:  "Title",
    name:   "title",
    widget: WidgetVariant.String
  },
  {
    label:  "Description",
    name:   "description",
    widget: WidgetVariant.Text
  },
  {
    label:  "Body",
    name:   "body",
    widget: WidgetVariant.Markdown
  }
]

export const makeFileConfigItem = (name?: string): SingletonConfigItem => ({
  fields: cloneDeep(exampleFields),
  file:   casual.word,
  label:  casual.word,
  name:   name || casual.word
})

export const makeTopLevelConfigItem = (
  name?: string,
  type?: "folder" | "files" | null,
  category?: string
): TopLevelConfigItem => {
  const randBool = Math.random() >= 0.5
  const configType =
    (!type && randBool) || type === "folder" ?
      { folder: casual.word } :
      {
        files: times(2).map(() => makeFileConfigItem())
      }
  return {
    fields:   cloneDeep(exampleFields),
    name:     name || casual.word,
    label:    casual.word,
    category: category || casual.word,
    ...configType
  }
}

export const makeEditableConfigItem = (
  name?: string,
  type?: "folder" | "file"
): EditableConfigItem => {
  const randBool = Math.random() >= 0.5
  const configType =
    (!type && randBool) || type === "folder" ?
      { folder: casual.word, category: casual.word } :
      {
        file: casual.word
      }
  return {
    fields: cloneDeep(exampleFields),
    name:   name || casual.word,
    label:  casual.word,
    ...configType
  }
}

export const makeRepeatableConfigItem = (
  name?: string
): RepeatableConfigItem => ({
  fields:         cloneDeep(exampleFields),
  name:           name || casual.word,
  label:          casual.word,
  label_singular: casual.word,
  category:       casual.word,
  folder:         casual.word
})

export const makeSingletonConfigItem = (
  name?: string
): SingletonConfigItem => ({
  fields: cloneDeep(exampleFields),
  name:   name || casual.word,
  label:  casual.word,
  file:   casual.word
})

export const makeSingletonsConfigItem = (
  name?: string
): SingletonsConfigItem => {
  return {
    name:     name || casual.word,
    label:    casual.word,
    category: casual.word,
    files:    [makeSingletonConfigItem()]
  }
}

export const makeWebsiteStarterConfig = (): WebsiteStarterConfig =>
  cloneDeep(exampleSiteConfig as WebsiteStarterConfig)

export const makeWebsiteStarter = (
  type = "course",
  status = WebsiteStarterStatus.Active
): WebsiteStarter => ({
  id:     incr.next().value,
  name:   casual.title,
  status: status,
  path:   casual.url,
  source: casual.word,
  commit: null,
  slug:   type,
  config: makeWebsiteStarterConfig()
})

export const makeWebsiteDetail = (
  overrides: Partial<Website> = {}
): Website => ({
  uuid:       casual.uuid,
  created_on: casual.moment.format(),
  updated_on: casual.moment.format(),
  name:       times(5)
    .map(() => casual.word)
    .join("-"),
  short_id: times(3)
    .map(() => casual.word)
    .join("-")
    .toLowerCase(),
  title:    casual.title,
  source:   null,
  starter:  makeWebsiteStarter("course"),
  metadata: {
    course_numbers: [`${casual.integer(1, 20)}.${casual.integer(1, 999)}`],
    term:           `${casual.month_name} ${casual.year}`
  },
  publish_date:                    casual.moment.format(),
  draft_publish_date:              casual.moment.format(),
  draft_url:                       casual.url,
  live_url:                        casual.url,
  gdrive_url:                      casual.url,
  has_unpublished_draft:           casual.boolean,
  has_unpublished_live:            casual.boolean,
  draft_publish_status:            null,
  live_publish_status:             null,
  draft_publish_status_updated_on: null,
  live_publish_status_updated_on:  null,
  sync_status:                     null,
  synced_on:                       null,
  sync_errors:                     null,
  is_admin:                        casual.boolean,
  content_warnings:                [],
  url_path:                        times(4)
    .map(() => casual.word)
    .join("-"),
  url_suggestion: "[sitemetadata:primary_course_number]-[sitemetdata:title]",
  s3_path:        `courses/${casual.word}`,
  ...overrides
})

export const makeWebsiteStatus = (
  website = makeWebsiteDetail()
): WebsiteStatus => {
  return {
    uuid:                            website.uuid,
    name:                            website.name,
    title:                           website.title,
    publish_date:                    website.publish_date,
    draft_publish_date:              website.draft_publish_date,
    has_unpublished_draft:           website.has_unpublished_draft,
    has_unpublished_live:            website.has_unpublished_live,
    live_publish_status:             website.live_publish_status,
    draft_publish_status:            website.draft_publish_status,
    live_publish_status_updated_on:  website.live_publish_status_updated_on,
    draft_publish_status_updated_on: website.draft_publish_status_updated_on,
    sync_status:                     null,
    synced_on:                       null,
    sync_errors:                     null
  }
}

export const makeWebsites = (n = WEBSITES_PAGE_SIZE): Website[] =>
  times(n).map(() => makeWebsiteDetail())

export const makeWebsiteListing = (
  websites: Website[],
  {
    previous = null,
    next = null
  }: { previous?: string | null; next?: string | null } = {}
): WebsiteListingResponse => {
  const count = websites.length
  const results = websites
  return { next, previous, results, count }
}

export const makeWebsiteCollaborator = (): WebsiteCollaborator => ({
  user_id: incr.next().value,
  name:    casual.name,
  email:   casual.email,
  role:    casual.random_element([ROLE_ADMIN, ROLE_EDITOR])
})

export const makePermanentWebsiteCollaborator = (): WebsiteCollaborator => ({
  user_id: incr.next().value,
  name:    casual.name,
  email:   casual.email,
  role:    casual.random_element([ROLE_GLOBAL, ROLE_OWNER])
})

export const makeWebsiteCollaborators = (): WebsiteCollaborator[] =>
  times(5).map(makeWebsiteCollaborator)

/**
 * Helper function for producing a random-ish ISO 8601-formatted
 * datetime string.
 *
 * This isn't _so_ random because it will only pick random dates
 * in the Unix epoch, but that should be good enough for testing :)
 */
const randomISO8601 = (): string =>
  new Date(casual.integer(0, Date.now())).toISOString()

export const makeWebsiteContentListItem = (): WebsiteContentListItem => ({
  text_id:    casual.uuid,
  title:      casual.title,
  type:       casual.word,
  updated_on: randomISO8601()
})

export const makeWebsiteContentDetail = (): WebsiteContent => ({
  ...makeWebsiteContentListItem(),
  markdown: casual.text,
  metadata: {
    description: casual.short_description
  },
  content_context: [],
  url_path:        casual.text
})
