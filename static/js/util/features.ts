/**
 * Returns the value of the flag.
 *
 * Uses features_default as a fallback, otherwise returns `defaultValue`.
 *
 * @param name Name of the feature flag.
 * @param defaultValue Default value for the flag.
 * @returns Whether or not a feature is enabled.
 */
export function isFeatureEnabled(name: string, defaultValue = false): boolean {
  return (
    (SETTINGS.features ?? {})[name] ?? SETTINGS.features_default ?? defaultValue
  )
}
