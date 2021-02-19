import { Website } from "../types/websites"

interface Websites {
  [key: string]: Website
}

export const websitesRequest = (name: string): any => ({
  url:       `/api/websites/${name}/`,
  transform: (body: Website) => ({
    websites: {
      [name]: body
    }
  }),
  update: {
    websites: (prev: Websites, next: Websites) => ({
      ...prev,
      ...next
    })
  }
})
