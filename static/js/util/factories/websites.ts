import casual from "casual-browserify"
import { cloneDeep, times } from "lodash"

import incrementer from "../incrementer"
import {
  ROLE_ADMIN,
  ROLE_EDITOR,
  ROLE_GLOBAL,
  ROLE_OWNER,
  WEBSITES_PAGE_SIZE
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
  WebsiteStarterConfig
} from "../../types/websites"

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
  times(5).map(() => makeWebsiteCollaborator())

export const makeWebsiteContentListItem = (): WebsiteContentListItem => ({
  text_id: casual.uuid,
  title:   casual.title,
  type:    casual.word
})

export const makeWebsiteContentDetail = (): WebsiteContent => ({
  ...makeWebsiteContentListItem(),
  markdown: casual.text,
  metadata: {
    description: casual.short_description
  }
})
