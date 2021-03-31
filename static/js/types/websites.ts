import { ROLE_ADMIN, ROLE_EDITOR, ROLE_GLOBAL, ROLE_OWNER } from "../constants"

export enum WidgetVariant {
  Markdown = "markdown",
  File = "file",
  Boolean = "boolean",
  Text = "text",
  String = "string",
  Select = "select"
}

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
}

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
  collections: ConfigItem[]
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
  metadata: any
  is_admin?: boolean // eslint-disable-line
}

type WebsiteRoleEditable = typeof ROLE_ADMIN | typeof ROLE_EDITOR
type WebsiteRole = typeof ROLE_GLOBAL | typeof ROLE_OWNER | WebsiteRoleEditable

export interface WebsiteCollaborator {
  role: WebsiteRole
  group: string
  username: string
  email: string
  name: string
}

export interface WebsiteCollaboratorFormData {
  email?: string
  role: WebsiteRoleEditable
}

export interface WebsiteContentListItem {
  uuid: string
  title: string | null
  type: string
}

export interface WebsiteContent extends WebsiteContentListItem {
  markdown: string | null
  metadata: null | { [key: string]: string }
}
