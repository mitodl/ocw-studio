/* eslint-disable prefer-template */
import { editor } from "@ckeditor/ckeditor5-core"
import Markdown from "./Markdown"
import { createTestEditor, htmlConvertContainsTest } from "./test_util"
import MathSyntax from "./MathSyntax"

const getEditor = createTestEditor([MathSyntax, Markdown])

describe("Conversion to and from html for Inline mode", () => {
  const math = String.raw`\\(E=mc^2\\)`
  const markdown = (start: string, mid: string, end: string) =>
    String.raw`${start ?? ""}This is a ${mid ?? ""}text markdown${end ?? ""}`
  const scriptTag = '<script type="math/tex">E=mc^2</script>'
  const htmlString = (start: string, mid: string, end: string) =>
    `<p>${start ?? ""}This is a ${mid ?? ""}text markdown${end ?? ""}</p>`
  let editor: editor.Editor

  beforeAll(async () => {
    editor = await getEditor()
  })

  it.each([
    {
      markdownTestString: markdown(math, "", ""),
      htmlTestString:     htmlString(scriptTag, "", "")
    },
    {
      markdownTestString: markdown("", math, ""),
      htmlTestString:     htmlString("", scriptTag, "")
    },
    {
      markdownTestString: markdown("", "", math),
      htmlTestString:     htmlString("", "", scriptTag)
    }
  ])(
    "Should check script tag in multiple positions, inline mode",
    async ({ markdownTestString, htmlTestString }) => {
      htmlConvertContainsTest(editor, markdownTestString, htmlTestString)
    }
  )
})

describe("Conversion to and from html for Display mode", () => {
  const math = String.raw`\\[E=mc^2\\]`
  const markdown = (start: string, mid: string, end: string) =>
    String.raw`${start ?? ""}This is a ${mid ?? ""}text markdown${end ?? ""}`
  const scriptTag = '<script type="math/tex; mode=display">E=mc^2</script>'
  const htmlString = (start: string, mid: string, end: string) =>
    `<p>${start ?? ""}This is a ${mid ?? ""}text markdown${end ?? ""}</p>`
  let editor: editor.Editor

  beforeAll(async () => {
    editor = await getEditor()
  })

  it.each([
    {
      markdownTestString: markdown(math, "", ""),
      htmlTestString:     htmlString(scriptTag, "", "")
    },
    {
      markdownTestString: markdown("", math, ""),
      htmlTestString:     htmlString("", scriptTag, "")
    },
    {
      markdownTestString: markdown("", "", math),
      htmlTestString:     htmlString("", "", scriptTag)
    }
  ])(
    "Should check script tag in multiple positions, display mode",
    async ({ markdownTestString, htmlTestString }) => {
      htmlConvertContainsTest(editor, markdownTestString, htmlTestString)
    }
  )
})
