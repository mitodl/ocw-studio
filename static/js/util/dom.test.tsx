import React from "react"
import ReactDOMServer from "react-dom/server"
import { mockMatchMedia } from "../test_util"
import { scrollToElement } from "./dom"

describe("scrollToError", () => {
  const stringToHtml = (string: string): HTMLElement => {
    const template = document.createElement("template")
    template.innerHTML = string.trim()
    const node = template.content.firstChild
    if (node instanceof HTMLElement) return node
    throw new Error("Expected an HTMLElement")
  }
  const getTestPage = () => {
    const page = stringToHtml(
      ReactDOMServer.renderToStaticMarkup(
        <div>
          <form id="form-1">
            <div id="div-1a"></div>
            <div id="div-1b" className="form-error"></div>
            <div id="div-1c" className="form-error meow"></div>
          </form>
          <form id="form-2">
            <div id="div-2a" className="form-error meow"></div>
            <div id="div-2b" className="form-error"></div>
            <div id="div-2c"></div>
          </form>
        </div>
      )
    )
    const [form1, form2] = ["#form-1", "#form-2"].map(s =>
      page.querySelector(s)
    ) as HTMLElement[]
    const [div1b, div1c, div2a] = ["#div-1b", "#div-1c", "#div-2a"].map(s =>
      page.querySelector(s)
    ) as HTMLElement[]
    const elements = [form1, form2, div1b, div1c, div2a]
    expect(elements.every(e => e instanceof HTMLElement)).toBe(true)

    // js-dom does not currently implement scrollIntoView
    div1b.scrollIntoView = jest.fn()
    div1c.scrollIntoView = jest.fn()
    div2a.scrollIntoView = jest.fn()

    return {
      containers: { form1, form2, page },
      spies:      {
        div1b: {
          scrollIntoView: div1b.scrollIntoView,
          focus:          jest.spyOn(div1b, "focus")
        },
        div1c: {
          scrollIntoView: div1c.scrollIntoView,
          focus:          jest.spyOn(div1c, "focus")
        },
        div2a: {
          scrollIntoView: div2a.scrollIntoView,
          focus:          jest.spyOn(div2a, "focus")
        }
      }
    }
  }

  it("it scrolls to and focuses the first matching div in container", () => {
    mockMatchMedia()
    const { containers, spies } = getTestPage()

    scrollToElement(containers.form1, ".form-error")
    expect(spies.div1b.scrollIntoView).toHaveBeenCalledTimes(1)
    expect(spies.div1b.focus).toHaveBeenCalledTimes(1)

    scrollToElement(containers.form2, ".form-error")
    expect(spies.div2a.scrollIntoView).toHaveBeenCalledTimes(1)
    expect(spies.div2a.focus).toHaveBeenCalledTimes(1)

    scrollToElement(containers.page, ".meow")
    expect(spies.div1c.scrollIntoView).toHaveBeenCalledTimes(1)
    expect(spies.div1c.focus).toHaveBeenCalledTimes(1)
  })

  it("it smoothly scrolls to center by default", () => {
    mockMatchMedia()
    const { containers, spies } = getTestPage()

    scrollToElement(containers.form1, ".form-error")
    expect(spies.div1b.scrollIntoView).toHaveBeenCalledWith({
      behavior: "smooth",
      block:    "center"
    })
    expect(spies.div1b.focus).toHaveBeenCalledWith({ preventScroll: true })
  })

  it("it respects (prefers-reduced-motion: reduce)", () => {
    const matchMedia = mockMatchMedia()
    const { containers, spies } = getTestPage()

    matchMedia.mockImplementation(() => ({ matches: true }))

    scrollToElement(containers.form1, ".form-error")
    expect(matchMedia).toHaveBeenCalledWith("(prefers-reduced-motion: reduce)")
    expect(spies.div1b.scrollIntoView).toHaveBeenCalledWith({
      behavior: "auto",
      block:    "center"
    })
    expect(spies.div1b.focus).toHaveBeenCalledWith({ preventScroll: true })
  })

  it("it does not error when no element is found", () => {
    const matchMedia = mockMatchMedia()
    const { containers } = getTestPage()

    matchMedia.mockImplementation(() => ({ matches: true }))

    expect(() => scrollToElement(containers.page, ".not-there")).not.toThrow()
  })
})
