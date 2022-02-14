/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

export type Website = {
  uuid?: string
  readonly created_on?: string
  readonly updated_on?: string
  name: string
  short_id: string
  title: string
  source?: Website.source | null
  draft_publish_date?: string | null
  publish_date?: string | null
  metadata?: any
  readonly starter?: {
    readonly id?: number
    /**
     * Human-friendly name of the starter project.
     */
    name: string
    /**
     * Github repo path or local file path of the starter project.
     */
    path: string
    source: Website.source
    /**
     * Commit hash for the repo (if this commit came from a Github starter repo).
     */
    commit?: string | null
    /**
     * Short string that can be used to identify this starter.
     */
    slug: string
  }
  owner?: number | null
}

export namespace Website {
  export enum source {
    STUDIO = "studio",
    OCW_IMPORT = "ocw-import"
  }
}
