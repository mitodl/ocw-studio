import Markdown from "./Markdown"
import { createTestEditor } from "./test_util"
import { turndownService } from "../turndown"
import LegacyShortcodes from "./LegacyShortcodes"
import { LEGACY_SHORTCODES } from "./constants"
import Paragraph from "@ckeditor/ckeditor5-paragraph/src/paragraph"

const quizTestMD = `{{< quiz_multiple_choice questionId="Q1_div" >}}{{< quiz_choices >}}{{< quiz_choice isCorrect="false" >}}sound, satisfiable{{< /quiz_choice >}}{{< quiz_choice isCorrect="false" >}}valid, satisfiable{{< /quiz_choice >}}{{< quiz_choice isCorrect="true" >}}sound, valid{{< /quiz_choice >}}{{< quiz_choice isCorrect="false" >}}valid, true{{< /quiz_choice >}}{{< /quiz_choices >}}{{< quiz_solution / >}}{{< /quiz_multiple_choice >}}`

const getEditor = createTestEditor([Paragraph, LegacyShortcodes, Markdown])

describe("ResourceEmbed plugin", () => {
  afterEach(() => {
    turndownService.rules.array = turndownService.rules.array.filter(
      (rule: any) => !/LegacyShortcodeSyntax/.test(rule.name)
    )
    // @ts-ignore
    turndownService._customRulesSet = undefined
  })

  test.each(LEGACY_SHORTCODES)(
    "should take in and return %p shortcode",
    async shortcode => {
      const md = `{{< ${shortcode} >}}`
      const editor = await getEditor(md)
      // @ts-ignore
      expect(editor.getData()).toBe(md)
    }
  )

  test.each(LEGACY_SHORTCODES)(
    "should take in and return %p closing shortcode",
    async shortcode => {
      const md = `{{< /${shortcode} >}}`
      const editor = await getEditor(md)
      // @ts-ignore
      expect(editor.getData()).toBe(md)
    }
  )

  test.each(LEGACY_SHORTCODES)(
    "should take in and return %p shortcode with arguments",
    async shortcode => {
      const md = `{{< ${shortcode} arguments foo=123 html=<for some reason/> >}}`
      const editor = await getEditor(md)
      // @ts-ignore
      expect(editor.getData()).toBe(md)
    }
  )

  test("should support a quiz example", async () => {
    const editor = await getEditor(quizTestMD)
    // @ts-ignore
    expect(editor.getData()).toBe(quizTestMD)
  })
})
