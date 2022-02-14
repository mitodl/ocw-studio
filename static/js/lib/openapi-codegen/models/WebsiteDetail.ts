/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

export type WebsiteDetail = {
    readonly uuid?: string;
    readonly created_on?: string;
    readonly updated_on?: string;
    name: string;
    short_id: string;
    title: string;
    source?: WebsiteDetail.source | null;
    readonly draft_publish_date?: string;
    readonly publish_date?: string;
    metadata?: any;
    readonly starter?: {
        readonly id?: number;
        /**
         * Human-friendly name of the starter project.
         */
        name: string;
        /**
         * Github repo path or local file path of the starter project.
         */
        path: string;
        source: WebsiteDetail.source;
        /**
         * Commit hash for the repo (if this commit came from a Github starter repo).
         */
        commit?: string | null;
        /**
         * Short string that can be used to identify this starter.
         */
        slug: string;
        /**
         * Site config describing content types, widgets, etc.
         */
        config: any;
    };
    readonly owner?: string;
    readonly is_admin?: string;
    readonly draft_url?: string;
    readonly live_url?: string;
    readonly has_unpublished_live?: boolean;
    readonly has_unpublished_draft?: boolean;
    readonly gdrive_url?: string;
    readonly live_publish_status?: WebsiteDetail.live_publish_status;
    readonly live_publish_status_updated_on?: string;
    readonly draft_publish_status?: WebsiteDetail.draft_publish_status;
    readonly draft_publish_status_updated_on?: string;
    readonly sync_status?: string;
    readonly sync_errors?: any;
    readonly synced_on?: string;
    readonly content_warnings?: string;
};

export namespace WebsiteDetail {

    export enum source {
        STUDIO = 'studio',
        OCW_IMPORT = 'ocw-import',
    }

    export enum live_publish_status {
        SUCCEEDED = 'succeeded',
        PENDING = 'pending',
        STARTED = 'started',
        ERRORED = 'errored',
        ABORTED = 'aborted',
        NOT_STARTED = 'not-started',
    }

    export enum draft_publish_status {
        SUCCEEDED = 'succeeded',
        PENDING = 'pending',
        STARTED = 'started',
        ERRORED = 'errored',
        ABORTED = 'aborted',
        NOT_STARTED = 'not-started',
    }


}
