import UrlAssembler from "url-assembler"

import { WEBSITES_PAGE_SIZE } from "../constants"

// PAGE URLS
export const sitesBaseUrl = UrlAssembler().prefix("/sites/")
export const newSiteUrl = UrlAssembler().prefix("/new-site/")

export const siteDetailUrl = sitesBaseUrl.segment(":name/")
export const siteContentListingUrl = siteDetailUrl.segment("type/:contentType/")
export const siteCollaboratorsUrl = siteDetailUrl.segment("collaborators/")
export const siteCollaboratorsAddUrl = siteCollaboratorsUrl.segment("new/")
export const siteCollaboratorsDetailUrl = siteCollaboratorsUrl.segment(
  ":userId/"
)

export const collectionsBaseUrl = UrlAssembler().prefix("/collections/")

// API URLS
const api = UrlAssembler().prefix("/api/")

export const startersApi = api.segment("starters/")

// WEBSITES API
export const siteApi = api.segment("websites/")
export const siteApiDetailUrl = siteApi.segment(":name/")
export const siteApiActionUrl = siteApiDetailUrl.segment(":action/")

export const siteApiCollaboratorsUrl = siteApiDetailUrl.segment(
  "collaborators/"
)
export const siteApiCollaboratorsDetailUrl = siteApiCollaboratorsUrl.segment(
  ":userId/"
)
export const siteApiContentUrl = siteApiDetailUrl.segment("content/")
export const siteApiContentListingUrl = siteApiContentUrl.query({
  limit: WEBSITES_PAGE_SIZE
})
export const siteApiContentDetailUrl = siteApiContentUrl.segment(":textId/")
export const siteApiListingUrl = siteApi.query({
  limit: WEBSITES_PAGE_SIZE
})

// WEBSITE COLLECTIONS API

/**
 * Listing API URL for WebsiteCollection records
 **/
export const collectionsApiUrl = api.segment("collections/")

/**
 * Detail API URL for WebsiteCollection records
 *
 * Returns only a single WebsiteCollection record, but does
 * not include its items.
 **/
export const collectionsApiDetailUrl = collectionsApiUrl.segment(
  ":collection_id/"
)

/**
 * Listing API for WebsiteCollectionItems
 *
 * This looks like:
 *
 * /api/collections/:collection_id/items/
 *
 * It returns the items contained in a WebsiteCollection.
 **/
export const wcItemsApiUrl = collectionsApiDetailUrl.segment("items/")

/**
 * Detail API for WebsiteCollectionItems
 *
 * Detail view for a single WebsiteCollectionItem record.
 * this looks like:
 *
 * /api/collections/:collection_id/items/:item_id/
 *
 * It's mainly of use for changing the order of items in the
 * WebsiteCollection by editing the `position` attribute.
 * Note that if a single `WebsiteCollectionItem` has its position
 * changed the backend takes care of reconciling all the other items
 * in the list w/ that position change, so only one request is needed
 * to change an item's position.
 **/
export const wcItemsApiDetailUrl = wcItemsApiUrl.segment(":item_id/")
