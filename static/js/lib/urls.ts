export const siteUrl = (name: string): string => `/sites/${name}/`
export const siteComponentUrl = (name: string, configName: string): string =>
  `/sites/${name}/${configName}/`
