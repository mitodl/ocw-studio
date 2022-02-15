import { ContentListingParams } from "../types/websites"
import { contentListingKey } from "./websites"

describe("contentListingKey", () => {
  it("uses all param properties to make a key", () => {
    const contentListingParams: Required<ContentListingParams> = {
      name:         "0",
      offset:       1,
      type:         "2",
      search:       "3",
      resourcetype: "4",
      pageContent:  true,
      published:    true
    }
    expect(contentListingKey(contentListingParams)).toBe(
      '["0","2","3",true,1,"4",true]'
    )
  })
})
