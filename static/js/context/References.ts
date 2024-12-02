import React, { useContext } from "react"

/**
 * This allows us to set references context for a whole component
 * tree, starting, for instance, with our SiteContentForm component.
 * This makes it then easy to grab the current References from anywhere in
 * the component tree.
 *
 * The easiest way to use it is with the `useReferences` hook defined in
 * this file, like so:
 *
 * ```ts
 * import { useReferences } from '../context/References'
 *
 * const references = useReferences()
 * ```
 **/
const ReferencesContext = React.createContext<null>(null)
export default ReferencesContext

/**
 * A Utility hook for accessing the references context.
 *
 * This ensures that we're only reading from the context in a setting
 * where the component has an ancestor component setting the value.
 *
 * Additionally, this simplifies the typing of the context value. Since
 * we have a nice run-time guard against a null value we can safely type
 * the return value as `References`, instead of `References | null`.
 **/
export function useReferences() {
  const referencesContext = useContext(ReferencesContext)
  if (referencesContext === null) {
    throw new Error("useReferences must be within ReferencesContext.Provider")
  }

  return referencesContext
}
