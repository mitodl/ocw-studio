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

export interface WebsiteCollectionItem {
  position: number
}
