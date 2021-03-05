export const siteUrl = (name: string): string => `/sites/${name}/`
export const siteContentListingUrl = (
  name: string,
  configName: string
): string => `/sites/${name}/${configName}/`

export const siteCollaboratorsUrl = (name: string): string =>
  `/sites/${name}/settings/collaborators/`

export const siteCollaboratorsAddUrl = (name: string): string =>
  `${siteCollaboratorsUrl(name)}new/`

export const siteCollaboratorsDetailUrl = (
  name: string,
  username: string
): string => `${siteCollaboratorsUrl(name)}${username}/`

export const siteApiUrl = (name: string): string => `/api/websites/${name}/`
export const siteApiCollaboratorsUrl = (name: string): string =>
  `${siteApiUrl(name)}collaborators/`
export const siteApiCollaboratorsDetailUrl = (
  name: string,
  username: string
): string => `${siteApiCollaboratorsUrl(name)}${username}/`
