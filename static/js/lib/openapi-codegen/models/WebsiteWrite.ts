/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

export type WebsiteWrite = {
  uuid?: string
  readonly created_on?: string
  readonly updated_on?: string
  name: string
  short_id: string
  title: string
  source?: WebsiteWrite.source | null
  readonly draft_publish_date?: string
  readonly publish_date?: string
  metadata?: any
  starter: number
  owner?: number | null
}

export namespace WebsiteWrite {
  export enum source {
    STUDIO = "studio",
    OCW_IMPORT = "ocw-import"
  }
}
