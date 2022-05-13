import UrlAssembler from "./url-assembler"

import { WEBSITES_PAGE_SIZE } from "../constants"

export const logoutUrl = UrlAssembler.prefix("/logout")
export const loginUrl = UrlAssembler.prefix("/")

// PAGE URLS
export const sitesBaseUrl = UrlAssembler.prefix("/sites/")
export const newSiteUrl = UrlAssembler.prefix("/new-site/")

export const siteDetailUrl = sitesBaseUrl.segment(":name/")
export const siteContentListingUrl = siteDetailUrl.segment("type/:contentType/")
export const siteContentNewUrl = siteContentListingUrl.segment("new/")
export const siteContentDetailUrl = siteContentListingUrl.segment("edit/:uuid/")
export const siteCollaboratorsUrl = siteDetailUrl.segment("collaborators/")
export const siteCollaboratorsAddUrl = siteCollaboratorsUrl.segment("new/")
export const siteCollaboratorsDetailUrl = siteCollaboratorsUrl.segment(
  ":userId/"
)

// API URLS
const api = UrlAssembler.prefix("/api/")

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
  limit:  WEBSITES_PAGE_SIZE,
  offset: 0
})
export const siteApiContentSyncGDriveUrl = siteApiContentUrl.segment(
  "gdrive_sync/"
)
