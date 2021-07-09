/**
 * Abstract class which our ModalState variant classes inherit from.
 *
 * This lets us set up methods like `.editing`, `.adding`, etc which
 * we can use on all the subclasses to check which variant we're
 * dealing with.
 */
abstract class ModalStateVariant<T> {
  state = ""

  /**
   * Check whether this ModalStateVariant instance is an Editing or not.
   */
  editing(): this is Editing<T> {
    return this.state === "editing"
  }

  /**
   * Check whether this ModalStateVariant instance is an Adding or not.
   */
  adding(): this is Adding<T> {
    return this.state === "adding"
  }

  /**
   * Check whether this ModalStateVariant instance is a Closed or not.
   */
  closed(): this is Closed<T> {
    return this.state === "closed"
  }
}

/**
 * An Editing state, which provides for wrapping a value
 * related to the content being edited.
 */
class Editing<T> extends ModalStateVariant<T> {
  state: "editing" = "editing"
  /**
   * The value wrapped in the Editing state
   */
  wrapped: T
  constructor(wrapped: T) {
    super()
    this.wrapped = wrapped
  }
}

/**
 * Adding state, for when new content is being created.
 */
class Adding<T> extends ModalStateVariant<T> {
  state: "adding" = "adding"
}

/**
 * Closed state, for when the drawer is closed and deactivated.
 */
class Closed<T> extends ModalStateVariant<T> {
  state: "closed" = "closed"
}

/**
 * Represent the three possible states for the WebsiteCollection
 * adding / editing drawer.
 *
 * Use the `createModalState` helper function to simplify creating
 * instances of these types.
 *
 * Provides support for wrapping a value in the Editing state, which
 * can be used to store the ID of the object currently being edited
 * or something along those lines.
 **/
export type ModalState<T> = Editing<T> | Adding<T> | Closed<T>

/**
 * Helper function for creating ModalState objects
 * (these are used by the WebsiteCollection editing/
 * creation UI to represent possible drawer states).
 */
export function createModalState<T>(state: "adding", wrapped: null): Adding<T>
export function createModalState<T>(state: "closed", wrapped: null): Closed<T>
export function createModalState<T>(state: "editing", wrapped: T): Editing<T>
export function createModalState<T>(
  state: string,
  wrapped: T | null
): ModalState<T> {
  if (state === "editing") {
    // the overloading gives us some assurance that we can cast
    // wrapped to T here
    return new Editing(wrapped as T)
  }
  if (state === "adding") {
    return new Adding()
  }
  return new Closed()
}
