import * as React from "react"
import { shallow } from "enzyme"

import Header from "./Header"

describe("Header", () => {
  it("displays the name of the site", () => {
    const wrapper = shallow(<Header />)
    expect(wrapper.text()).toBe("OCW Studio")
  })
})
