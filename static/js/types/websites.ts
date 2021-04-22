import { ROLE_ADMIN, ROLE_EDITOR, ROLE_GLOBAL, ROLE_OWNER } from "../constants"

/**
 * The different widget variants supported in Site configurations
 **/
export enum WidgetVariant {
  Markdown = "markdown",
  File = "file",
  Boolean = "boolean",
  Text = "text",
  String = "string",
  Select = "select",
  Hidden = "hidden",
  Object = "object"
}

export interface FieldValueCondition {
  field: string
  equals: string
}

/**
 * A configuration for a field for site content. This type basically
 * contains the information needed to render the field in the UI, to edit it,
 * validate it, etc.
 **/
export interface ConfigField {
  name: string
  label: string
  widget: WidgetVariant
  minimal?: boolean
  help?: string
  required?: boolean
  default?: any
  min?: number
  max?: number
  options?: string[]
  multiple?: boolean
  condition?: FieldValueCondition
  fields?: ConfigField[]
  collapsed?: boolean
}

export interface BaseConfigItem {
  name: string
  label: string
}

export type SingletonConfigItem = BaseConfigItem & {
  file: string
  fields: ConfigField[]
}

export type SingletonsConfigItem = BaseConfigItem & {
  category: string
  files: Array<SingletonConfigItem>
}

export type RepeatableConfigItem = BaseConfigItem & {
  category: string
  folder: string
  fields: ConfigField[]
}

export type TopLevelConfigItem = RepeatableConfigItem | SingletonsConfigItem

export type EditableConfigItem = RepeatableConfigItem | SingletonConfigItem

export interface ConfigItem {
  name: string
  label: string
  category: string
  fields: ConfigField[]
  file?: string
  files?: Array<any>
  folder?: string
}

export interface WebsiteStarterConfig {
  collections: TopLevelConfigItem[]
}

export interface WebsiteStarter {
  id: number
  name: string
  path: string
  source: string
  commit: string | null
  slug: string
  config: WebsiteStarterConfig | null
}

export interface NewWebsitePayload {
  title: string
  starter: number
}

export interface Website {
  uuid: string
  created_on: string // eslint-disable-line
  updated_on: string // eslint-disable-line
  name: string
  title: string
  source: string | null
  starter: WebsiteStarter | null
  metadata?: any
  is_admin?: boolean // eslint-disable-line
}

type WebsiteRoleEditable = typeof ROLE_ADMIN | typeof ROLE_EDITOR
type WebsiteRole = typeof ROLE_GLOBAL | typeof ROLE_OWNER | WebsiteRoleEditable

export interface WebsiteCollaborator {
  user_id: number // eslint-disable-line
  role: WebsiteRole
  email: string
  name: string
}

export interface WebsiteCollaboratorFormData {
  email?: string
  role: WebsiteRoleEditable
}

export interface WebsiteContentListItem {
  text_id: string // eslint-disable-line
  title: string | null
  type: string
}

export interface WebsiteContent extends WebsiteContentListItem {
  markdown: string | null
  metadata: null | { [key: string]: string }
}

export interface ContentListingParams {
  name: string
  type: string
  offset: number
}
