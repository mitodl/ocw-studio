import { ModalState } from "./modal_state"

/**
 * A user-editable collection of Websites
 *
 * This is basically an array implemented using Django
 * records. We have a WebsiteCollection to store the list
 * metadata (title, description) and then WebsiteCollectionItem
 * records associate websites to the list.
 **/
export interface WebsiteCollection {
  title: string
  description: string
  id: number
}

/**
 * An entry in a WebsiteCollection
 **/
export interface WebsiteCollectionItem {
  position: number
}

/**
 * For the WebsiteCollection drawer we need to keep track
 * of a WebsiteCollection ID, which is set in the drawer
 * state if we're editing an existing collection.
 */
export type WebsiteCollectionModalState = ModalState<number>
