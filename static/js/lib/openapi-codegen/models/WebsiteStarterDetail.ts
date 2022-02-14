/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

export type WebsiteStarterDetail = {
    readonly id?: number;
    /**
     * Human-friendly name of the starter project.
     */
    name: string;
    /**
     * Github repo path or local file path of the starter project.
     */
    path: string;
    source: WebsiteStarterDetail.source;
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

export namespace WebsiteStarterDetail {

    export enum source {
        GITHUB = 'github',
        LOCAL = 'local',
    }


}
