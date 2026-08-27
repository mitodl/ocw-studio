import ClassicEditor from "@ckeditor/ckeditor5-editor-classic/src/classiceditor"
import { EditorConfig } from "@ckeditor/ckeditor5-core"

import {
  FullEditorConfig,
  MinimalEditorConfig,
  MinimalWithMathEditorConfig,
} from "./CKEditor"
import { RESOURCE_LINK_CONFIG_KEY, WEBSITE_NAME } from "./plugins/constants"

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
