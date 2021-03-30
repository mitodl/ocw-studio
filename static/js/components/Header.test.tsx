import * as React from "react"
import { shallow } from "enzyme"

import Header from "./Header"

describe("Header", () => {
  it("displays the name of the site", () => {
    const wrapper = shallow(<Header />)
    expect(wrapper.find("h2").text()).toBe("OCW Studio")
  })

  it("shows the user's name for logged in users", () => {
    const wrapper = shallow(<Header />)
    expect(wrapper.find("span").text()).toBe("Jane Doe")
  })

  it("shows a logout button for logged in users", () => {
    const wrapper = shallow(<Header />)
    expect(wrapper.find("a").text()).toBe("Logout")
  })
})
