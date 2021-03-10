import { WEBSITES_PAGE_SIZE } from "../constants"

export const newSiteUrl = (): string => "/new-site/"
export const siteListingUrl = (offset: number): string =>
  offset ? `/sites/?offset=${offset}` : "/sites/"
export const siteDetailUrl = (name: string): string => `/sites/${name}/`
export const siteContentListingUrl = (
  name: string,
  contentType: string
): string => `/sites/${name}/${contentType}/`

export const siteCollaboratorsUrl = (name: string): string =>
  `/sites/${name}/settings/collaborators/`

export const siteCollaboratorsAddUrl = (name: string): string =>
  `${siteCollaboratorsUrl(name)}new/`

export const siteCollaboratorsDetailUrl = (
  name: string,
  username: string
): string => `${siteCollaboratorsUrl(name)}${username}/`

export const siteApiListingUrl = (offset: number): string =>
  `/api/websites/?limit=${WEBSITES_PAGE_SIZE}&offset=${offset}`
export const siteApiDetailUrl = (name: string): string =>
  `/api/websites/${name}/`
export const siteApiCollaboratorsUrl = (name: string): string =>
  `${siteApiDetailUrl(name)}collaborators/`
export const siteApiCollaboratorsDetailUrl = (
  name: string,
  username: string
): string => `${siteApiCollaboratorsUrl(name)}${username}/`
export const siteAddContentUrl = (name: string, contentType: string): string =>
  `/sites/${name}/${contentType}/add/`

export const siteApiContentUrl = (name: string): string =>
  `${siteApiDetailUrl(name)}content/`
export const siteApiContentDetailUrl = (name: string, uuid: string): string =>
  `${siteApiContentUrl(name)}${uuid}/`
