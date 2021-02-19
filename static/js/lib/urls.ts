export const siteUrl = (name: string): string => `/sites/${name}/`
export const siteContentListingUrl = (name: string, configName: string): string =>
  `/sites/${name}/${configName}/`
