/* eslint-disable camelcase */
/* eslint-disable one-var */
/* eslint-disable no-var */

interface SETTINGS {
  reactGaDebug: string;
  gaTrackingID: string;
  public_path: string;
  environment: string;
  release_version: string;
  sentry_dsn: string;
  gdrive_enabled: bool;
  /**
   * Settings.user does exist, but leaving it untyped to help encourage using
   * `store.user` instead.
   */
  // user: User | null;
}
export declare global {

  declare var SETTINGS: SETTINGS

  declare var RELEASE_YEAR: string

  declare var _testing: boolean

  // eslint-disable-next-line @typescript-eslint/ban-types
  declare var __REDUX_DEVTOOLS_EXTENSION__: Function

  declare var __webpack_public_path__: string
}
