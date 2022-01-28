import React from "react"
import { shallow } from "enzyme"
import { StudioListItem } from "./StudioList"

describe("StudioListItem", () => {
  it("does not have hover-pointer class if onClick not provided", () => {
    const wrapper = shallow(
      <StudioListItem title="some-titlle" subtitle="meow" />
    )

    expect(wrapper.find("li").hasClass("hover-pointer")).toBe(false)
  })

  it("does have hover-pointer class if onClick is provided", () => {
    const wrapper = shallow(
      <StudioListItem title="some-titlle" subtitle="meow" onClick={jest.fn} />
    )

    expect(wrapper.find("li").hasClass("hover-pointer")).toBe(true)
  })
})
