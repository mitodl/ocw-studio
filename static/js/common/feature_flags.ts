/**
 * PostHog feature flag keys used throughout the application.
 */

/**
 * Controls whether content can be deleted in the Studio UI.
 * When enabled, allows deletion of content types specified in
 * OCW_STUDIO_DELETABLE_CONTENT_TYPES setting.
 */
export const FEATURE_FLAG_CONTENT_DELETABLE = "OCW_STUDIO_CONTENT_DELETABLE"

/**
 * Controls whether the "Add Video Resource" feature is enabled.
 * When enabled, allows users to add video resources through the UI.
 */
export const FEATURE_FLAG_ADD_VIDEO_RESOURCE = "OCW_STUDIO_ADD_VIDEO_RESOURCE"

/**
 * Controls whether the custom link UI is enabled in the Markdown editor.
 * When enabled, uses the CustomLink plugin for enhanced link editing.
 */
export const FEATURE_FLAG_CUSTOM_LINKUI = "OCW_STUDIO_CUSTOM_LINKUI_ENABLE"
