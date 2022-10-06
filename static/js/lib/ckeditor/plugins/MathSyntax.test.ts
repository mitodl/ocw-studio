/* eslint-disable prefer-template */
import Markdown from "./Markdown"
import { createTestEditor, htmlConvertContainsTest } from "./test_util"
import MathSyntax from "./MathSyntax"

const getEditor = createTestEditor([
  MathSyntax,
  Markdown
])

describe("Conversion to and from html for Inline mode", ()=>{
  it("should add a valid script tag", async () => {
    const editor = await getEditor()

    const markdown = "This is a text markdown"
    const mathStartOfLine = String.raw`\\(E=mc^2\\) ${markdown}`
    const html = '<p><script type="math/tex">E=mc^2</script> This is a text markdown</p>'
    htmlConvertContainsTest(editor, mathStartOfLine, html)
  })
})
