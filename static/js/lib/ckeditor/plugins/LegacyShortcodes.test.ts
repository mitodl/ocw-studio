import Markdown from "./Markdown"
import { createTestEditor } from "./test_util"
import { turndownService } from "../turndown"
import LegacyShortcodes from "./LegacyShortcodes"
import { LEGACY_SHORTCODES } from "./constants"
import Paragraph from "@ckeditor/ckeditor5-paragraph/src/paragraph"

const quizTestMD = `{{< quiz_multiple_choice questionId="Q1_div" >}}{{< quiz_choices >}}{{< quiz_choice isCorrect="false" >}}sound, satisfiable{{< /quiz_choice >}}{{< quiz_choice isCorrect="false" >}}valid, satisfiable{{< /quiz_choice >}}{{< quiz_choice isCorrect="true" >}}sound, valid{{< /quiz_choice >}}{{< quiz_choice isCorrect="false" >}}valid, true{{< /quiz_choice >}}{{< /quiz_choices >}}{{< quiz_solution >}}{{< /quiz_multiple_choice >}}`

const getEditor = createTestEditor([Paragraph, LegacyShortcodes, Markdown])

describe("ResourceEmbed plugin", () => {
  afterEach(() => {
    turndownService.rules.array = turndownService.rules.array.filter(
      (rule: any) => !/LegacyShortcodeSyntax/.test(rule.name),
    )
  })

  test.each(LEGACY_SHORTCODES)(
    "should take in and return %p shortcode",
    async (shortcode) => {
      const md = `{{< ${shortcode} >}}`
      const editor = await getEditor(md)
      expect(editor.getData()).toBe(md)
    },
  )

  test.each(LEGACY_SHORTCODES)(
    "should take in and return %p closing shortcode",
    async (shortcode) => {
      const md1 = `{{< /${shortcode} >}}`
      const editor1 = await getEditor(md1)
      expect(editor1.getData()).toBe(md1)

      /**
       * Hugo documentation uses the first version so it should be preferred.
       * But Hugo accepts this version and image-gallery uses it.
       * The editor will normalize it to the first version.
       */
      const md2 = `{{</ ${shortcode} >}}`
      const editor2 = await getEditor(md2)
      expect(editor2.getData()).toBe(md1)
    },
  )

  test.each(LEGACY_SHORTCODES)(
    "should take in and return %p shortcode with positional parameters",
    async (shortcode) => {
      const md = `{{< ${shortcode} arguments "and chemistry H{{< sub 2 >}}0" >}}`
      const expected = `{{< ${shortcode} "arguments" "and chemistry H{{< sub 2 >}}0" >}}`
      const editor = await getEditor(md)
      expect(editor.getData()).toBe(expected)
    },
  )

  test.each(LEGACY_SHORTCODES)(
    "should take in and return %p shortcode with named parameters",
    async (shortcode) => {
      const md = `{{< ${shortcode} foo=123 html="<for some reason/>" >}}`
      const expected = `{{< ${shortcode} foo="123" html="<for some reason/>" >}}`
      const editor = await getEditor(md)
      expect(editor.getData()).toBe(expected)
    },
  )

  test("should support a quiz example", async () => {
    const editor = await getEditor(quizTestMD)
    expect(editor.getData()).toBe(quizTestMD)
  })
})
