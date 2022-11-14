import Markdown, { MarkdownDataProcessor } from "./Markdown"

import { createTestEditor, getConverters, markdownTest } from "./test_util"

import { TEST_MARKDOWN, TEST_HTML } from "../../../test_constants"
import MarkdownSyntaxPlugin from "./MarkdownSyntaxPlugin"
import { ShowdownExtension } from "showdown"
import { TurndownRule } from "../../../types/ckeditor_markdown"

describe("Markdown CKEditor plugin", () => {
  const getEditor = createTestEditor([Markdown])

  it("should have a name", () => {
    expect(Markdown.pluginName).toBe("Markdown")
  })

  describe("basic Markdown support", () => {
    it("should set editor.data.processor", async () => {
      const editor = await getEditor("")
      expect(editor.data.processor).toBeInstanceOf(MarkdownDataProcessor)
    })

    it("should provide for bi-directional translation", async () => {
      const editor = await getEditor("")
      markdownTest(editor, TEST_MARKDOWN, TEST_HTML)
    })
  })
})

describe("Multiple Markdown CKEditors", () => {
  /**
   * A markdown plugin that inteprets all HTML paragraphs as a particular animal
   * sound...
   *
   * The goal here is to construct two conflicting plugins (say, CatPlugin and
   * DogPlugin) and demonstrate two separate editors can each independently use
   * one of the conflicting plugins.
   */
  abstract class AnimalParagraphSyntax extends MarkdownSyntaxPlugin {
    abstract sound: string
    abstract pluginName: string

    get showdownExtension(): () => ShowdownExtension[] {
      return () => []
    }

    get turndownRules(): TurndownRule[] {
      return [
        {
          name: this.plugin_name,
          rule: {
            filter:      "p",
            replacement: content => {
              const sound = this.sound
              const sounds = sound.repeat(
                Math.ceil(content.length / sound.length)
              )
              return `${sounds}!`
            }
          }
        }
      ]
    }
  }

  /**
   * Meow!
   */
  class CatParagraphSyntax extends AnimalParagraphSyntax {
    pluginName = "cat_paragraphs"
    sound = "meow"
  }

  /**
   * Woof!
   */
  class DogParagraphSyntax extends AnimalParagraphSyntax {
    pluginName = "dog_paragraphs"
    sound = "woof"
  }

  const getCatEditor = createTestEditor([CatParagraphSyntax, Markdown])
  const getDogEditor = createTestEditor([DogParagraphSyntax, Markdown])

  test("Separate editors can use conflciting turndown plugins", async () => {
    const catEditor = await getCatEditor()
    const dogEditor = await getDogEditor()
    const cat = getConverters(catEditor)
    const dog = getConverters(dogEditor)

    const paragraph = "<p>1234567890</p>"

    expect(cat.html2md(paragraph)).toBe("meowmeowmeow!")
    expect(dog.html2md(paragraph)).toBe("woofwoofwoof!")
  })

  test("Separate editors can use conflicting allowedHtml lists", async () => {
    const subEditor = await createTestEditor([Markdown], {
      "markdown-config": { allowedHtml: ["sub"] }
    })()
    const supEditor = await createTestEditor([Markdown], {
      "markdown-config": { allowedHtml: ["sup"] }
    })()

    const sub = getConverters(subEditor)
    const sup = getConverters(supEditor)

    const paragraph = "<p>Hello world sub<sub>123</sub> sup<sup>abc</sup>!</p>"

    expect(sub.html2md(paragraph)).toBe("Hello world sub<sub>123</sub> supabc!")
    expect(sup.html2md(paragraph)).toBe("Hello world sub123 sup<sup>abc</sup>!")
  })
})
