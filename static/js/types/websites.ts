/* eslint-disable camelcase */
import {
  GoogleDriveSyncStatuses,
  PublishStatus,
  ROLE_ADMIN,
  ROLE_EDITOR,
  ROLE_GLOBAL,
  ROLE_OWNER,
  WebsiteStarterStatus,
} from "../constants"
import { SiteFormValue } from "./forms"
import { ModalState } from "./modal_state"

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
  Object = "object",
  Relation = "relation",
  Menu = "menu",
  HierarchicalSelect = "hierarchical-select",
  WebsiteCollection = "website-collection",
}

export interface FieldValueCondition {
  field: string
  equals: string
}

/**
 * A configuration for a field for site content.This is a 'base' interface
 * which the actual interfaces for each type of field extend.
 **/
interface ConfigFieldBaseProps {
  name: string
  label: string
  required?: boolean
  help?: string
  default?: any
  widget: WidgetVariant
  condition?: FieldValueCondition
}

export interface MarkdownConfigField extends ConfigFieldBaseProps {
  widget: WidgetVariant.Markdown
  minimal?: boolean
  link?: string[]
  embed?: string[]
  allowed_html?: string[]
}

export interface FileConfigField extends ConfigFieldBaseProps {
  widget: WidgetVariant.File
}

export interface BooleanConfigField extends ConfigFieldBaseProps {
  widget: WidgetVariant.Boolean
}

export interface TextConfigField extends ConfigFieldBaseProps {
  widget: WidgetVariant.Text
}

export interface StringConfigField extends ConfigFieldBaseProps {
  widget: WidgetVariant.String
}

export interface HiddenConfigField extends ConfigFieldBaseProps {
  widget: WidgetVariant.Hidden
}

export interface WebsiteCollectionConfigField extends ConfigFieldBaseProps {
  widget: WidgetVariant.WebsiteCollection
}

export interface SelectConfigField extends ConfigFieldBaseProps {
  widget: WidgetVariant.Select
  options: string[]
  multiple?: boolean
  min?: number
  max?: number
}

export interface ObjectConfigField extends ConfigFieldBaseProps {
  widget: WidgetVariant.Object
  fields: ConfigField[]
  collapsed?: boolean
}

export interface HierarchicalSelectConfigField extends ConfigFieldBaseProps {
  widget: WidgetVariant.HierarchicalSelect
  options_map: Record<string, any>
  min?: number
  max?: number
}

/**
 * This captures the different types of RelationFilters we
 * support. As of now it is just equality, but see this issue
 * for some details:
 * https://github.com/mitodl/ocw-studio/issues/289
 **/
export enum RelationFilterVariant {
  Equals = "equals",
}

/**
 * A record containing the information needed to filter entries
 * in a WidgetVariant.Relation field. Entries which match the
 * filter (on `field`) defined here will be excluded from the
 * UI.
 **/
export interface RelationFilter {
  field: string
  filter_type: RelationFilterVariant
  value: SiteFormValue
}

export interface RelationConfigField extends ConfigFieldBaseProps {
  widget: WidgetVariant.Relation
  collection: string
  display_field: string
  multiple?: boolean
  min?: number
  max?: number
  filter?: RelationFilter
  website?: string
  sortable?: boolean
  cross_site?: boolean
}

export interface MenuConfigField extends ConfigFieldBaseProps {
  widget: WidgetVariant.Menu
  collections: string[]
}

/**
 * A configuration for a field for site content. This type basically
 * contains the information needed to render the field in the UI, to edit it,
 * validate it, etc.
 **/
export type ConfigField =
  | MarkdownConfigField
  | FileConfigField
  | BooleanConfigField
  | TextConfigField
  | StringConfigField
  | HiddenConfigField
  | SelectConfigField
  | ObjectConfigField
  | RelationConfigField
  | MenuConfigField
  | HierarchicalSelectConfigField
  | WebsiteCollectionConfigField

export interface BaseConfigItem {
  name: string
  label: string
  label_singular?: string
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
  label_singular?: string
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
  status: WebsiteStarterStatus
  path: string
  source: string
  commit: string | null
  slug: string
  config: WebsiteStarterConfig | null
}

export interface NewWebsitePayload {
  title: string
  short_id: string
  starter: number
}

export interface WebsiteStatus {
  uuid: string
  name: string
  title: string
  /** ISO 8601 datetime string or null */
  publish_date: string | null
  /** ISO 8601 datetime string or null */
  draft_publish_date: string | null
  has_unpublished_draft: boolean
  has_unpublished_live: boolean
  live_publish_status: PublishStatus | null
  live_publish_status_updated_on: string | null
  draft_publish_status: PublishStatus | null
  draft_publish_status_updated_on: string | null
  sync_status: GoogleDriveSyncStatuses | null
  synced_on: string | null
  sync_errors: Array<string> | null
  unpublished: boolean
}

export type Website = WebsiteStatus & {
  uuid: string
  created_on: string
  updated_on: string
  name: string
  title: string
  short_id: string
  source: string | null
  starter: WebsiteStarter | null
  metadata?: any
  is_admin?: boolean
  draft_url: string
  live_url: string
  gdrive_url: string | null
  has_unpublished_draft: boolean
  has_unpublished_live: boolean
  content_warnings?: Array<string>
  url_path: string | null
  url_suggestion: string
  s3_path: string | null
}

type WebsiteRoleEditable = typeof ROLE_ADMIN | typeof ROLE_EDITOR
type WebsiteRole = typeof ROLE_GLOBAL | typeof ROLE_OWNER | WebsiteRoleEditable

export interface WebsiteCollaborator {
  user_id: number
  role: WebsiteRole
  email: string
  name: string
}

export interface WebsiteCollaboratorFormData {
  email?: string
  role: WebsiteRole | ""
}

export interface WebsiteContentListItem {
  text_id: string
  title: string | null
  type: string
  /** ISO 8601 formatted datetime string */
  updated_on: string
}

export interface WebsiteContent extends WebsiteContentListItem {
  markdown: string | null
  metadata: null | Record<string, SiteFormValue>
  content_context: WebsiteContent[] | null
  file?: string
  url_path?: string
}

export interface ContentListingParams {
  name: string
  type?: string | string[]
  pageContent?: boolean
  offset: number
  search?: string
  resourcetype?: string
  published?: boolean
}

export interface CollaboratorListingParams {
  name: string
  pageContent?: boolean
  offset: number
}

export interface ContentDetailParams {
  name: string
  textId: string
}

export interface CollaboratorDetailParams {
  name: string
  userId: number
}

export enum LinkType {
  Internal = "internal",
  External = "external",
}

/**
 * For the WebsiteContent drawer we need to keep track of a
 * content ID when we're editing existing content.
 */
export type WebsiteContentModalState = ModalState<string>

export type WebsiteDropdown = {
  id: string
  label: string
  clickHandler: (...args: any[]) => void
}

export interface WebsiteInitials {
  name: string
  title: string
  short_id: string
}
