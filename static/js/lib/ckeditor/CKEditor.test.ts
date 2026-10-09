import ClassicEditor from "@ckeditor/ckeditor5-editor-classic/src/classiceditor"
import { EditorConfig } from "@ckeditor/ckeditor5-core"

import {
  FullEditorConfig,
  MinimalEditorConfig,
  MinimalWithMathEditorConfig,
  MinimalWithSubSupEditorConfig,
} from "./CKEditor"
import {
  MARKDOWN_CONFIG_KEY,
  RESOURCE_LINK_CONFIG_KEY,
  WEBSITE_NAME,
} from "./plugins/constants"

/**
 * Characterization tests. These boot each real editor config so that a plugin
 * failing to load, or a toolbar item losing its factory, is caught by CI rather
 * than by manual smoke testing.
 */
const REQUIRED_CONFIG = {
  [RESOURCE_LINK_CONFIG_KEY]: {
    hrefTemplate: "https://example.com/courses/test-site/",
  },
  [WEBSITE_NAME]: "test-site",
}

interface EditorConfigUnderTest {
  plugins: NonNullable<EditorConfig["plugins"]>
  toolbar: { items: string[] }
  image?: { toolbar: string[] }
  table?: { contentToolbar: string[] }
}

/**
 * Every toolbar item a config asks for, main toolbar and widget toolbars alike.
 *
 * The widget toolbars matter more than they look. CKEditor only resolves them
 * in `WidgetToolbarRepository#_showToolbar`, which runs the first time an image
 * or table is selected, so an unresolvable item there logs nothing at boot and
 * the warning assertion below cannot see it. `imageStyle:full` sat in
 * `image.toolbar` unresolvable for years for exactly that reason.
 */
const allToolbarItems = (config: EditorConfigUnderTest): string[] =>
  [
    ...config.toolbar.items,
    ...(config.image?.toolbar ?? []),
    ...(config.table?.contentToolbar ?? []),
  ].filter((item) => item !== "|")

const createEditor = (config: EditorConfigUnderTest) =>
  ClassicEditor.create("", { ...config, ...REQUIRED_CONFIG })

/**
 * Third tuple entry is every warning the config is currently expected to log
 * while booting. All three configs are expected to boot silently; a non-empty
 * list here would mean a known, deliberately tolerated warning.
 */
const CONFIGS: [string, EditorConfigUnderTest, string[]][] = [
  ["FullEditorConfig", FullEditorConfig, []],
  ["MinimalEditorConfig", MinimalEditorConfig, []],
  ["MinimalWithMathEditorConfig", MinimalWithMathEditorConfig, []],
  ["MinimalWithSubSupEditorConfig", MinimalWithSubSupEditorConfig, []],
]

/** CKEditor appends this argument to every warning it logs. */
const DOCS_LINK_PREFIX = "\nRead more:"

const describeArg = (arg: unknown): string => {
  if (typeof arg === "string") return arg
  try {
    return JSON.stringify(arg)
  } catch {
    return String(arg)
  }
}

describe.each(CONFIGS)("%s", (_name, config, expectedWarnings) => {
  let warnSpy: jest.SpyInstance

  beforeEach(() => {
    // CKEditor warns via console.warn, which jest-fail-on-console turns into an
    // opaque failure. Capture the warnings so they can be asserted on instead.
    warnSpy = jest.spyOn(console, "warn").mockImplementation(() => undefined)
  })

  afterEach(() => {
    warnSpy.mockRestore()
  })

  /**
   * Every console.warn call, flattened to a readable one-liner. Only CKEditor's
   * boilerplate docs-link argument is dropped; no call is filtered out, so an
   * unexpected warning of any kind fails the assertion below and names itself
   * in the diff.
   */
  const warnings = (): string[] =>
    warnSpy.mock.calls.map((call) =>
      call
        .filter(
          (arg: unknown) =>
            !(typeof arg === "string" && arg.startsWith(DOCS_LINK_PREFIX)),
        )
        .map(describeArg)
        .join(" "),
    )

  it("instantiates every plugin without error", async () => {
    const editor = await createEditor(config)
    expect(editor).toBeTruthy()
    await editor.destroy()
  })

  it("registers a UI factory for every configured toolbar item", async () => {
    const editor = await createEditor(config)
    const items = allToolbarItems(config)

    expect(items.length).toBeGreaterThan(0)
    items.forEach((item) => {
      expect([item, editor.ui.componentFactory.has(item)]).toEqual([item, true])
    })

    await editor.destroy()
  })

  it("logs no warnings beyond the known ones while booting", async () => {
    const editor = await createEditor(config)

    expect(warnings()).toEqual(expectedWarnings)

    await editor.destroy()
  })
})

/**
 * A syntax plugin only reaches the data processor if it is constructed before
 * `Markdown`: it publishes its showdown extension and turndown rules from its
 * constructor, and `Markdown` reads that config in its own constructor.
 * CKEditor constructs plugins in the order the `plugins` array lists them, so
 * the array order silently decides whether legacy shortcodes survive a round
 * trip. Nothing warns when they do not -- the editor boots clean and the
 * corruption only shows up in saved Markdown -- so assert the behaviour here.
 */
describe("MinimalWithSubSupEditorConfig round trips its own syntax", () => {
  /**
   * `sub`/`sup` only survive turndown via keep(allowedHtml), so a field using
   * this variant is expected to set `allowed_html: ["sub", "sup"]`. Spread
   * rather than inlined, because these OCW keys are not on `EditorConfig`.
   */
  const SUBSUP_MARKDOWN_CONFIG = {
    [MARKDOWN_CONFIG_KEY]: { allowedHtml: ["sub", "sup"] },
  }

  const createSubSupEditor = () =>
    ClassicEditor.create("", {
      ...MinimalWithSubSupEditorConfig,
      ...REQUIRED_CONFIG,
      ...SUBSUP_MARKDOWN_CONFIG,
    })

  it.each([
    ["subscript markup", "Water H<sub>2</sub>O"],
    ["superscript markup", "x<sup>2</sup>"],
  ])("preserves %s", async (_label, markdown) => {
    const editor = await createSubSupEditor()
    editor.setData(markdown)
    expect(editor.getData().trim()).toEqual(markdown)
    await editor.destroy()
  })

  /**
   * Hugo only recognises the `{{<` delimiter unescaped. Params come back
   * quoted, which is how `FullEditorConfig` has always re-emitted them, so the
   * assertion pins the delimiter rather than the exact input string.
   */
  it.each([
    ["sub", "Water H{{< sub 2 >}}O", 'Water H{{< sub "2" >}}O'],
    ["sup", "x{{< sup 2 >}}", 'x{{< sup "2" >}}'],
    [
      "resource_file",
      "{{< resource_file uuid-1234 >}}",
      '{{< resource_file "uuid-1234" >}}',
    ],
  ])(
    "keeps the %s shortcode delimiter intact",
    async (_label, markdown, expected) => {
      const editor = await createSubSupEditor()
      editor.setData(markdown)
      expect(editor.getData().trim()).toEqual(expected)
      await editor.destroy()
    },
  )
})

/**
 * Same plugin-order hazard as above, twice over. `ImageGallery` must be listed
 * before `Markdown`, or a gallery is saved with escaped `{{\<` delimiters. And
 * it must come before every other syntax plugin: showdown runs extensions in
 * the order the plugins are constructed, and one that ran first could rewrite
 * text inside a gallery's params before the gallery captures them, as
 * MathSyntax would with the caption below.
 */
describe("FullEditorConfig round trips an image gallery", () => {
  it("keeps every param, whatever other syntax plugins would make of it", async () => {
    const editor = await ClassicEditor.create("", {
      ...FullEditorConfig,
      ...REQUIRED_CONFIG,
    })
    const items = [
      String.raw`{{< image-gallery-item href="6525d0e9d7a6a5d4ae6eb7b45d2f4bc4_gallery2-2.jpg" data-ngdesc="" text="The walls of our {{% resource_link \"c2956690-7ead-4f56-8282-fe998b987b00\" \"TEAL classroom\" %}} are lined with whiteboards." >}}`,
      '{{< image-gallery-item uuid="0b3a1d6e-9f0c-4b8e-8d5e-2f1c7a9e4b21" href="pyrite.jpg" data-ngdesc="Pyrite" text="Pyrite: FeS{{< sub 2 >}}" >}}',
      String.raw`{{< image-gallery-item href="circle.jpg" text="Area \\(\\pi r^2\\)" >}}`,
    ]
    editor.setData(
      [
        '{{< image-gallery id="788b6153-ce75-e1be-31f0-a394ce761f32_nanogallery2" baseUrl="/courses/18-05-introduction-to-probability-and-statistics-spring-2014/" >}}',
        ...items,
        "{{</ image-gallery >}}",
      ].join("\n"),
    )
    expect(editor.getData().trim()).toEqual(
      [
        '{{< image-gallery id="788b6153-ce75-e1be-31f0-a394ce761f32_nanogallery2" baseUrl="/courses/18-05-introduction-to-probability-and-statistics-spring-2014/" >}}',
        ...items,
        "{{< /image-gallery >}}",
      ].join("\n"),
    )
    await editor.destroy()
  })

  /**
   * Showdown's GitHub flavor treats `\<` as the start of an escaped HTML tag
   * and swallows everything up to the next `>`, which can be the end of a link
   * converted later in the document, taking its title with it. A real 12.114
   * caption carries `\<1`; inside a gallery it is encoded before showdown sees
   * it, so a link after the gallery must come through intact.
   */
  it("keeps an escaped less-than inside a gallery from breaking a link after it", async () => {
    const editor = await ClassicEditor.create("", {
      ...FullEditorConfig,
      ...REQUIRED_CONFIG,
    })
    const markdown = [
      '{{< image-gallery baseUrl="/courses/12-114-field-geology-i-fall-2005/" >}}',
      String.raw`{{< image-gallery-item href="b86a4dd13c56f6fc8e263fb2fa123363_lec2photo5.jpg" data-ngdesc="" text="They are 1.5 by to \<1 b.y. old." >}}`,
      "{{< /image-gallery >}}",
      "",
      'See {{% resource_link "43712d3a-92cf-48c1-8a22-54b9d59d6dd7" "Inspiration" %}} here.',
    ].join("\n")
    editor.setData(markdown)
    expect(editor.getData().trim()).toEqual(markdown)
    await editor.destroy()
  })
})
