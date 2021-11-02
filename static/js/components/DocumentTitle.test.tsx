import DocumentTitle, { formatTitle } from "./DocumentTitle"
import { mount } from "enzyme"
import React from "react"

describe("DocumentTitle component", () => {
  const render = (title: string) => mount(<DocumentTitle title={title} />)

  it("formatTitle should format titles correctly", () => {
    expect(formatTitle()).toBe("OCW Studio")
    expect(formatTitle("Site Page")).toBe("OCW Studio | Site Page")
    expect(formatTitle("Site Page", "Edit")).toBe(
      "OCW Studio | Site Page | Edit"
    )
  })

  it("should mount and set the title", () => {
    render("test title")
    expect(document.title).toBe("test title")
  })
})
