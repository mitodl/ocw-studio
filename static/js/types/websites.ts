export interface ConfigField {
  name: string
  label: string
  widget: string
}

export interface ConfigItem {
  name: string
  label: string
  fields: ConfigField[]
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
}
