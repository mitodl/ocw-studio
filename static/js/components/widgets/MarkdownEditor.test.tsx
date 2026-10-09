import React from "react"
import { render, screen, act } from "@testing-library/react"
import ClassicEditor from "@ckeditor/ckeditor5-editor-classic/src/classiceditor"
import sinon, { SinonSandbox } from "sinon"
import { omit } from "ramda"

import MarkdownEditor from "./MarkdownEditor"
import {
  FullEditorConfig,
  MinimalEditorConfig,
  MinimalWithMathEditorConfig,
  MinimalWithSubSupEditorConfig,
} from "../../lib/ckeditor/CKEditor"
import {
  ADD_IMAGE_GALLERY,
  ADD_RESOURCE_EMBED,
  ADD_RESOURCE_LINK,
  CKEDITOR_RESOURCE_UTILS,
  IMAGE_GALLERY_COMMAND,
  ImageGalleryHandle,
  MARKDOWN_CONFIG_KEY,
  MINIMAL_WITH_MATH,
  MINIMAL_WITH_SUBSUP,
  RESOURCE_EMBED,
  RESOURCE_LINK,
  RESOURCE_LINK_CONFIG_KEY,
  WEBSITE_NAME,
} from "../../lib/ckeditor/plugins/constants"
import { getMockEditor } from "../../test_util"
import { useWebsite } from "../../context/Website"
import {
  makeWebsiteContentDetail,
  makeWebsiteDetail,
  makeWebsiteStarter,
} from "../../util/factories/websites"
import { WebsiteContent } from "../../types/websites"
import ResourceLink from "../../lib/ckeditor/plugins/ResourceLink"

jest.mock("../../lib/ckeditor/CKEditor", () => {
  const originalModule = jest.requireActual("../../lib/ckeditor/CKEditor")

  return {
    __esModule: true,
    ...originalModule,
    createResourceLink: jest.fn(),
  }
})
jest.mock("../../context/Website", () => {
  const originalModule = jest.requireActual("../../context/Website")
  return {
    __esModule: true,
    ...originalModule,
    useWebsite: jest.fn(),
  }
})

jest.mock("@ckeditor/ckeditor5-inspector")

let lastCKEditorProps: any = null
jest.mock("@ckeditor/ckeditor5-react", () => ({
  CKEditor: (props: any) => {
    lastCKEditorProps = props
    return <div data-testid="ckeditor" />
  },
}))

let lastResourcePickerProps: any = null
jest.mock("../../components/widgets/ResourcePickerDialog", () => ({
  __esModule: true,
  ...jest.requireActual("../../components/widgets/ResourcePickerDialog"),
  default: (props: any) => {
    lastResourcePickerProps = props
    return props.isOpen ? <div data-testid="resource-picker" /> : null
  },
}))

jest.mock("./EmbeddedResource", () => ({
  __esModule: true,
  default: ({ uuid }: { uuid: string }) => (
    <div data-testid="embedded-resource">{uuid}</div>
  ),
}))

const renderMarkdownEditor = (props: any = {}) => {
  lastCKEditorProps = null
  lastResourcePickerProps = null
  return render(
    <MarkdownEditor allowedHtml={[]} link={[]} embed={[]} {...props} />,
  )
}

const mocUseWebsite = jest.mocked(useWebsite)

describe("MarkdownEditor", () => {
  let sandbox: SinonSandbox

  beforeEach(() => {
    sandbox = sinon.createSandbox()
    const website = makeWebsiteDetail()
    mocUseWebsite.mockReturnValue(website)
  })

  afterEach(() => {
    sandbox.restore()
  })

  it.each([
    {
      minimal: true,
      expectedConfig: MinimalEditorConfig,
      configLabel: "MinimalEditorConfig",
    },
    {
      minimal: false,
      expectedConfig: FullEditorConfig,
      configLabel: "FullEditorConfig",
      otherProps: { allowedHtml: ["sub", "sup"] },
    },
    {
      minimal: MINIMAL_WITH_MATH,
      expectedConfig: MinimalWithMathEditorConfig,
      configLabel: "MinimalWithMathEditorConfig",
    },
    {
      minimal: MINIMAL_WITH_SUBSUP,
      expectedConfig: MinimalWithSubSupEditorConfig,
      configLabel: "MinimalWithSubSupEditorConfig",
      otherProps: { allowedHtml: ["sub", "sup"] },
    },
  ])(
    "Uses the $configLabel when minimal=$minimal",
    ({ minimal, expectedConfig, otherProps }) => {
      renderMarkdownEditor({
        minimal,
        /**
         * MarkdownEditor dynamically modifies the config a bit.
         * In order to more closely equal MinimalEditorConfig/FullEditorConfig,
         * we need at least one embed and one link.
         */
        embed: ["resource"],
        link: ["page"],
        ...otherProps,
      })
      expect(lastCKEditorProps.editor).toBe(ClassicEditor)
      const rawConfig = lastCKEditorProps.config
      const config = omit(
        [
          CKEDITOR_RESOURCE_UTILS,
          MARKDOWN_CONFIG_KEY,
          RESOURCE_LINK_CONFIG_KEY,
          WEBSITE_NAME,
        ],
        rawConfig,
      )
      expect(config).toEqual(expectedConfig)
    },
  )

  it.each([
    { value: "some value", expectedData: "some value" },
    { value: null, expectedData: "" },
  ])(
    "renders CKEditor with data=$expectedData when value=$value",
    ({ value, expectedData }) => {
      renderMarkdownEditor({ value })
      expect(lastCKEditorProps.data).toBe(expectedData)
    },
  )

  it("should delegate to ResourceLink.createResourceLink when inserting a link", async () => {
    renderMarkdownEditor({ link: ["page"] })
    const editor = getMockEditor()
    const resourceLinkPlugin = { createResourceLink: jest.fn() }
    editor.plugins.get.mockImplementation((val: unknown) => {
      if (val === ResourceLink) return resourceLinkPlugin
      return null
    })
    lastCKEditorProps.onReady(editor)
    lastResourcePickerProps.insertEmbed(
      "best-uuid-ever",
      "some title",
      "resourceLink",
    )
    expect(resourceLinkPlugin.createResourceLink).toHaveBeenCalledWith(
      "best-uuid-ever",
      "some title",
    )
  })

  it.each([
    { link: [], embed: [], shouldExist: false },
    { link: ["page"], embed: [], shouldExist: true },
    { link: [], embed: ["resource"], shouldExist: true },
    { link: ["page"], embed: ["resource"], shouldExist: true },
  ])(
    "should render ResourcePickerDialog iff link or embed are nonempty",
    ({ link, embed, shouldExist }) => {
      renderMarkdownEditor({ link, embed })
      expect(lastResourcePickerProps !== null).toBe(shouldExist)
    },
  )

  it("should render resources with using EmbeddedResource", async () => {
    renderMarkdownEditor()
    const el = document.createElement("div")
    document.body.appendChild(el)
    await act(async () => {
      lastCKEditorProps.config[CKEDITOR_RESOURCE_UTILS].renderResource(
        "resource-uuid",
        el,
      )
    })
    expect(screen.getByTestId("embedded-resource")).toBeInTheDocument()
    expect(screen.getByTestId("embedded-resource")).toHaveTextContent(
      "resource-uuid",
    )
    document.body.removeChild(el)
  })

  it.each([
    { embed: [], hasTool: false },
    { embed: ["resource"], hasTool: true },
  ])(
    'should show "add resource" iff embed is nonempty. Case: $embed',
    ({ embed, hasTool }) => {
      renderMarkdownEditor({ embed })
      expect(
        lastCKEditorProps.config.toolbar.items.includes(ADD_RESOURCE_EMBED),
      ).toBe(hasTool)
    },
  )

  it.each([
    { link: [], hasTool: false },
    { link: ["page"], hasTool: true },
  ])(
    'should show "add link" iff link is nonempty. Case: $link',
    ({ link, hasTool }) => {
      renderMarkdownEditor({ link })
      expect(
        lastCKEditorProps.config.toolbar.items.includes(ADD_RESOURCE_LINK),
      ).toBe(hasTool)
    },
  )

  it.each([
    { tool: "superscript", tag: "sup", allowedHtml: ["sup"], hasTool: true },
    { tool: "superscript", tag: "sup", allowedHtml: [], hasTool: false },
    { tool: "subscript", tag: "sub", allowedHtml: ["sub"], hasTool: true },
    { tool: "subscript", tag: "sub", allowedHtml: [], hasTool: false },
  ])(
    "includes $toolbar if and only if $tag is allowed. Allowed html: $allowedHtml",
    ({ tool, hasTool, allowedHtml }) => {
      renderMarkdownEditor({ minimal: false, allowedHtml })
      const items = lastCKEditorProps.config.toolbar.items

      expect(items.includes(tool)).toBe(hasTool)
    },
  )

  it.each([
    { slug: "course", hasTool: true },
    { slug: "ocw-www", hasTool: false },
  ])(
    "shows the image gallery button only on course sites (starter $slug)",
    ({ slug, hasTool }) => {
      SETTINGS.ocwCourseStarterSlug = "course"
      mocUseWebsite.mockReturnValue(
        makeWebsiteDetail({ starter: makeWebsiteStarter(slug) }),
      )
      renderMarkdownEditor({ minimal: false })
      expect(
        lastCKEditorProps.config.toolbar.items.includes(ADD_IMAGE_GALLERY),
      ).toBe(hasTool)
    },
  )

  it.each([
    { urlPath: "courses/18-05-intro", urlSuggestion: "", disabled: false },
    {
      urlPath: null,
      urlSuggestion: "18-05-[sitemetadata:term]",
      disabled: true,
    },
  ])(
    "disables new galleries while a course has no URL (url_path $urlPath)",
    ({ urlPath, urlSuggestion, disabled }) => {
      mocUseWebsite.mockReturnValue(
        makeWebsiteDetail({
          url_path: urlPath, // eslint-disable-line camelcase
          url_suggestion: urlSuggestion, // eslint-disable-line camelcase
        }),
      )
      renderMarkdownEditor({ minimal: false })
      expect(
        Boolean(
          lastCKEditorProps.config[CKEDITOR_RESOURCE_UTILS]
            .imageGalleryDisabledReason,
        ),
      ).toBe(disabled)
    },
  )

  it("recreates CKEditor when editorConfig changes", () => {
    const { rerender } = render(
      <MarkdownEditor embed={[]} link={[]} allowedHtml={[]} minimal={false} />,
    )
    const initialConfig = JSON.stringify(lastCKEditorProps.config)
    rerender(
      <MarkdownEditor
        embed={["resource"]}
        link={[]}
        allowedHtml={[]}
        minimal={false}
      />,
    )
    const newConfig = JSON.stringify(lastCKEditorProps.config)
    expect(newConfig).not.toEqual(initialConfig)
  })
  ;[RESOURCE_EMBED, RESOURCE_LINK].forEach((resourceNodeType) => {
    it(`should open the resource picker for ${resourceNodeType}`, async () => {
      renderMarkdownEditor({
        embed: ["resource"],
        link: ["resource", "page"],
      })
      await act(async () => {
        lastCKEditorProps.config[CKEDITOR_RESOURCE_UTILS].openResourcePicker(
          resourceNodeType,
        )
      })
      expect(lastResourcePickerProps.mode).toBe(resourceNodeType)
    })
  })

  describe("adding images to a gallery", () => {
    const image = (
      textId: string,
      file: string,
      caption: string,
    ): WebsiteContent => ({
      ...makeWebsiteContentDetail(),
      text_id: textId,
      file,
      metadata: {
        resourcetype: "Image",
        image_metadata: { "image-alt": "", caption, credit: "" },
      },
    })

    const openGalleryPicker = async (handle: ImageGalleryHandle | null) => {
      const editor = { ...getMockEditor(), execute: jest.fn() }
      renderMarkdownEditor()
      lastCKEditorProps.onReady(editor)
      await act(async () => {
        lastCKEditorProps.config[
          CKEDITOR_RESOURCE_UTILS
        ].openImageGalleryPicker(handle)
      })
      return editor
    }

    it.each([
      {
        urlPath: "courses/18-05-intro-spring-2014",
        urlSuggestion: "",
        params: ' baseUrl="/courses/18-05-intro-spring-2014/" ',
      },
      {
        urlPath: null,
        urlSuggestion: "18-05-[sitemetadata:term]",
        params: " ",
      },
    ])(
      "creates a new gallery with params '$params' when url_path is $urlPath",
      async ({ urlPath, urlSuggestion, params }) => {
        mocUseWebsite.mockReturnValue(
          makeWebsiteDetail({
            url_path: urlPath, // eslint-disable-line camelcase
            url_suggestion: urlSuggestion, // eslint-disable-line camelcase
          }),
        )
        const editor = await openGalleryPicker(null)
        await act(async () => {
          lastResourcePickerProps.insertMultiple([
            image(
              "u1",
              "https://bucket.s3.amazonaws.com/courses/x/pyrite.jpg",
              "Pyrite: FeS{{< sub 2 >}}",
            ),
          ])
        })
        expect(editor.execute).toHaveBeenCalledWith(IMAGE_GALLERY_COMMAND, {
          params,
          items: [
            ' uuid="u1" href="pyrite.jpg" text="Pyrite: FeS{{< sub 2 >}}" ',
          ],
        })
      },
    )

    it("keeps each widget with its own gallery when an earlier gallery is deleted", async () => {
      const { unmount } = renderMarkdownEditor()
      const makeGallery = (items: string[]) => {
        const el = document.createElement("div")
        document.body.appendChild(el)
        const handle: ImageGalleryHandle = {
          getItems: () => items,
          setItems: jest.fn(),
          onModelChange: () => () => undefined,
          openPicker: jest.fn(),
        }
        return { el, handle }
      }
      const first = makeGallery([' href="first.jpg" '])
      const second = makeGallery([' href="second.jpg" '])
      const { renderImageGallery } =
        lastCKEditorProps.config[CKEDITOR_RESOURCE_UTILS]
      await act(async () => {
        renderImageGallery(first.el, first.handle)
        renderImageGallery(second.el, second.handle)
      })
      expect(second.el.textContent).toContain("second.jpg")

      // CKEditor discards the deleted gallery's element; the next change
      // drops its widget.
      first.el.remove()
      await act(async () => {
        lastCKEditorProps.onChange(null, { getData: () => "" })
      })

      expect(second.el.textContent).toContain("second.jpg")
      expect(second.el.textContent).not.toContain("first.jpg")
      unmount()
    })

    it("leaves images already in the gallery out of the picker", async () => {
      const handle: ImageGalleryHandle = {
        getItems: () => [
          ' uuid="u1" href="pyrite.jpg" text="Pyrite" ',
          ' href="legacy.jpg" data-ngdesc="" text="Old" ',
        ],
        setItems: jest.fn(),
        onModelChange: () => () => undefined,
        openPicker: jest.fn(),
      }
      await openGalleryPicker(handle)
      const { isExcluded } = lastResourcePickerProps
      expect(isExcluded(image("u1", "https://b/x/pyrite.jpg", ""))).toBe(true)
      expect(isExcluded(image("u2", "https://b/x/legacy.jpg", ""))).toBe(true)
      expect(isExcluded(image("u3", "https://b/x/quartz.jpg", ""))).toBe(false)

      // A new gallery has nothing to leave out.
      await openGalleryPicker(null)
      expect(lastResourcePickerProps.isExcluded).toBeUndefined()
    })

    it("appends to an existing gallery, skipping images it already has", async () => {
      const setItems = jest.fn()
      const handle: ImageGalleryHandle = {
        getItems: () => [
          ' uuid="u1" href="pyrite.jpg" text="Pyrite" ',
          ' href="legacy.jpg" data-ngdesc="" text="Old" ',
        ],
        setItems,
        onModelChange: () => () => undefined,
        openPicker: jest.fn(),
      }
      const editor = await openGalleryPicker(handle)
      await act(async () => {
        lastResourcePickerProps.insertMultiple([
          image("u1", "https://bucket/courses/x/pyrite.jpg", "Pyrite"),
          image("u2", "https://bucket/courses/x/legacy.jpg", "Old"),
          image("u3", "https://bucket/courses/x/quartz.jpg", "Quartz"),
        ])
      })
      expect(setItems).toHaveBeenCalledWith([
        ' uuid="u1" href="pyrite.jpg" text="Pyrite" ',
        ' href="legacy.jpg" data-ngdesc="" text="Old" ',
        ' uuid="u3" href="quartz.jpg" text="Quartz" ',
      ])
      expect(editor.execute).not.toHaveBeenCalled()
    })
  })

  //
  ;[
    ["name", "name"],
    [null, ""],
  ].forEach(([name, expectedPropName]) => {
    ;[true, false].forEach((hasOnChange) => {
      it(`triggers ${
        hasOnChange ? "with" : "without"
      } an onChange when name=${String(name)}`, async () => {
        const onChangeStub = sandbox.stub()
        renderMarkdownEditor({
          name,
          onChange: hasOnChange ? onChangeStub : null,
        })

        const data = "some data"
        const editor = { getData: sandbox.stub().returns(data) }
        await act(async () => {
          lastCKEditorProps.onChange(null, editor)
        })
        if (hasOnChange) {
          sinon.assert.calledOnceWithExactly(onChangeStub, {
            target: { value: data, name: expectedPropName },
          })
        } else {
          expect(onChangeStub.called).toBe(false)
        }
      })
    })
  })
})
