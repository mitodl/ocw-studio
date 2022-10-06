/* eslint-disable prefer-template */
import Markdown from "./Markdown"
import Mathematics from 'ckeditor5-math/src/math'
import { createTestEditor, htmlConvertContainsTest } from "./test_util"
import ParagraphPlugin from "@ckeditor/ckeditor5-paragraph/src/paragraph"
import MathSyntax from "./MathSyntax"

const getEditor = createTestEditor([
  Mathematics,
  ParagraphPlugin,
  MathSyntax,
  Markdown
])

describe("Conversion to and from html for Inline mode", ()=>{
  it("should add a valid script tag", async () => {
    const editor = await getEditor()

    const markdown = "This is a text markdown"
    const mathStartOfLine = "\\(E=mc_2 \\)" + markdown
    const html = '<script type="math/tex">E=mc_2</script>'
    htmlConvertContainsTest(editor, mathStartOfLine, html)
  })
})
