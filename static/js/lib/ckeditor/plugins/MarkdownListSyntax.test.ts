import Markdown from "./Markdown"
import { createTestEditor, markdownTest } from "./test_util"
import ParagraphPlugin from "@ckeditor/ckeditor5-paragraph/src/paragraph"
import MarkdownListSyntax from "./MarkdownListSyntax"

const getEditor = createTestEditor([
  ParagraphPlugin,
  MarkdownListSyntax,
  Markdown,
])

describe("list conversion to and from html", () => {
  it("should not add paragraphs inside lists", async () => {
    const editor = await getEditor("")

    const markdown = `
- aardvark
- see [SO Question](https://meta.stackexchange.com/a/40978/394026) for info re trailing double spaces
- beaver  
      
    bear  
      
    battletoad
- chickadee
    `.trim()
    const html = `
<ul>
    <li>aardvark</li>
    <li>see <a href="https://meta.stackexchange.com/a/40978/394026">SO Question</a> for info re trailing double spaces</li>
    <li>beaver  <br><br>
        bear  <br><br>
        battletoad</li>
    <li>chickadee</li>
</ul>
    `

    markdownTest(editor, markdown, html)
  })

  it("should not add paragraphs inside lists, even when nested", async () => {
    const editor = await getEditor("")

    const markdown = `
- item 1  
      
    detail 1
- item 2:  
      
    [detail 2](ocw.mit.edu) is a link  
      
    - item 2a  
          
        detail 2a
    - item 2b
- item 3
    `.trim()
    const html = `
<ul>
    <li>item 1 <br><br>
        detail 1</li>
    <li>item 2: <br><br>
        <a href="ocw.mit.edu">detail 2</a> is a link <br><br>
        <ul>
            <li>item 2a <br><br>
                detail 2a</li>
            <li>item 2b</li>
        </ul>
    </li>
    <li>item 3</li>
</ul>
    `

    markdownTest(editor, markdown, html)
  })
})
