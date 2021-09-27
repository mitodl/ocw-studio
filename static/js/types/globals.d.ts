/* eslint-disable */
//
interface SETTINGS {
  reactGaDebug: string;
  gaTrackingID: string;
  public_path: string;
  environment: string;
  release_version: string;
  sentry_dsn: string;
  gdrive_enabled: bool;
  user: {
    username: string;
    email: string;
    name: string;
  } | null;
}

declare var SETTINGS: SETTINGS;

declare var _testing: boolean;

declare var __REDUX_DEVTOOLS_EXTENSION__: Function;

declare var __webpack_public_path__: string;
