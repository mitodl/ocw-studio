import React from "react"
import { shallow } from "enzyme"
import ClassicEditor from "@ckeditor/ckeditor5-editor-classic/src/classiceditor"
import { CKEditor } from "@ckeditor/ckeditor5-react"
import sinon, { SinonSandbox } from "sinon"
import { omit } from "ramda"

import MarkdownEditor from "./MarkdownEditor"
import {
  FullEditorConfig,
  MinimalEditorConfig
} from "../../lib/ckeditor/CKEditor"
import {
  ADD_RESOURCE_EMBED,
  ADD_RESOURCE_LINK,
  CKEDITOR_RESOURCE_UTILS,
  MARKDOWN_CONFIG_KEY,
  RESOURCE_EMBED,
  RESOURCE_LINK,
  RESOURCE_LINK_CONFIG_KEY
} from "../../lib/ckeditor/plugins/constants"
import ResourcePickerDialog from "../../components/widgets/ResourcePickerDialog"
import { getMockEditor } from "../../test_util"
import { useWebsite } from "../../context/Website"
import { makeWebsiteDetail } from "../../util/factories/websites"
import ResourceLink from "../../lib/ckeditor/plugins/ResourceLink"

jest.mock("../../lib/ckeditor/CKEditor", () => {
  const originalModule = jest.requireActual("../../lib/ckeditor/CKEditor")

  return {
    __esModule:         true,
    ...originalModule,
    insertResourceLink: jest.fn()
  }
})
jest.mock("../../context/Website", () => {
  const originalModule = jest.requireActual("../../context/Website")
  return {
    __esModule: true,
    ...originalModule,
    useWebsite: jest.fn()
  }
})

jest.mock("@ckeditor/ckeditor5-inspector")

jest.mock("@ckeditor/ckeditor5-react", () => ({
  CKEditor: () => <div />
}))

const render = (props = {}) => {
  return shallow(
    <MarkdownEditor allowedHtml={[]} link={[]} embed={[]} {...props} />
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
      minimal:        true,
      expectedConfig: MinimalEditorConfig,
      configLabel:    "MinimalEditorConfig"
    },
    {
      minimal:        false,
      expectedConfig: FullEditorConfig,
      configLabel:    "FullEditorConfig",
      otherProps:     { allowedHtml: ["sub", "sup"] }
    }
  ])(
    "Uses the $configLabel when minimal=$minimal",
    ({ minimal, expectedConfig, otherProps }) => {
      const wrapper = render({
        minimal,
        /**
         * MarkdownEditor dynamically modifies the config a bit.
         * In order to more closely equal MinimalEditorConfig/FullEditorConfig,
         * we need at least one embed and one link.
         */
        embed: ["resource"],
        link:  ["page"],
        ...otherProps
      })
      const ckWrapper = wrapper.find(CKEditor)
      expect(ckWrapper.prop("editor")).toBe(ClassicEditor)
      const config = omit(
        [
          CKEDITOR_RESOURCE_UTILS,
          MARKDOWN_CONFIG_KEY,
          RESOURCE_LINK_CONFIG_KEY
        ],
        ckWrapper.prop("config")
      )
      expect(config).toEqual(expectedConfig)
    }
  )

  it.each([
    { value: "some value", expectedData: "some value" },
    { value: null, expectedData: "" }
  ])(
    "renders CKEditor with data=$expectedData when value=$value",
    ({ value, expectedData }) => {
      const wrapper = render({ value })
      const ckWrapper = wrapper.find(CKEditor)
      expect(ckWrapper.prop("data")).toBe(expectedData)
    }
  )

  it("should delegate to ResourceLink.insertResourceLink when inserting a link", async () => {
    const wrapper = render({ link: ["page"] })
    const editorComponent = wrapper.find<{ onReady:(e: unknown) => void }>(
      CKEditor
    )
    const editor = getMockEditor()
    const resourceLinkPlugin = { insertResourceLink: jest.fn() }
    editor.plugins.get.mockImplementation((val: unknown) => {
      if (val === ResourceLink) return resourceLinkPlugin
      return null
    })
    editorComponent.prop("onReady")(editor)
    const picker = wrapper.find(ResourcePickerDialog)
    picker.prop("insertEmbed")("best-uuid-ever", "some title", "resourceLink")
    expect(resourceLinkPlugin.insertResourceLink).toHaveBeenCalledWith(
      "best-uuid-ever",
      "some title"
    )
  })

  it.each([
    { link: [], embed: [], shouldExist: false },
    { link: ["page"], embed: [], shouldExist: true },
    { link: [], embed: ["resource"], shouldExist: true },
    { link: ["page"], embed: ["resource"], shouldExist: true }
  ])(
    "should render ResourcePickerDialog iff link or embed are nonempty",
    ({ link, embed, shouldExist }) => {
      const wrapper = render({ link, embed })
      const resourcePicker = wrapper.find("ResourcePickerDialog")
      expect(resourcePicker.exists()).toBe(shouldExist)
    }
  )

  it("should render resources with using EmbeddedResource", () => {
    const wrapper = render()
    const editor = wrapper.find("CKEditor").prop("config")
    const el = document.createElement("div")
    // @ts-expect-error CKEditor types are a work in progress
    editor[CKEDITOR_RESOURCE_UTILS].renderResource("resource-uuid", el)
    wrapper.update()
    expect(
      wrapper
        .find("EmbeddedResource")
        .at(0)
        .prop("uuid")
    ).toEqual("resource-uuid")
  })

  it.each([
    { embed: [], hasTool: false },
    { embed: ["resource"], hasTool: true }
  ])(
    'should show "add resource" iff embed is nonempty. Case: $embed',
    ({ embed, hasTool }) => {
      const wrapper = render({ embed })
      const editorConfig = wrapper.find("CKEditor").prop("config")
      // @ts-expect-error CKEditor types are a work in progress
      expect(editorConfig.toolbar.items.includes(ADD_RESOURCE_EMBED)).toBe(
        hasTool
      )
    }
  )

  it.each([
    { link: [], hasTool: false },
    { link: ["page"], hasTool: true }
  ])(
    'should show "add link" iff link is nonempty. Case: $link',
    ({ link, hasTool }) => {
      const wrapper = render({ link })
      const editorConfig = wrapper.find("CKEditor").prop("config")
      // @ts-expect-error CKEditor types are a work in progress
      expect(editorConfig.toolbar.items.includes(ADD_RESOURCE_LINK)).toBe(
        hasTool
      )
    }
  )

  it.each([
    { tool: "superscript", tag: "sup", allowedHtml: ["sup"], hasTool: true },
    { tool: "superscript", tag: "sup", allowedHtml: [], hasTool: false },
    { tool: "subscript", tag: "sub", allowedHtml: ["sub"], hasTool: true },
    { tool: "subscript", tag: "sub", allowedHtml: [], hasTool: false }
  ])(
    "includes $toolbar if and only if $tag is allowed. Allowed html: $allowedHtml",
    ({ tool, hasTool, allowedHtml }) => {
      const wrapper = render({ minimal: false, allowedHtml })
      const ckWrapper = wrapper.find(CKEditor)
      const items = (ckWrapper.prop("config") as any).toolbar.items

      expect(items.includes(tool)).toBe(hasTool)
    }
  )

  //
  ;[RESOURCE_EMBED, RESOURCE_LINK].forEach(resourceNodeType => {
    it(`should open the resource picker for ${resourceNodeType}`, () => {
      const wrapper = render({
        embed: ["resource"],
        link:  ["resource", "page"]
      })
      const editor = wrapper.find("CKEditor").prop("config")
      // @ts-expect-error CKEditor types are a work in progress
      editor[CKEDITOR_RESOURCE_UTILS].openResourcePicker(resourceNodeType)
      wrapper.update()
      expect(
        wrapper
          .find("ResourcePickerDialog")
          .at(0)
          .prop("mode")
      ).toBe(resourceNodeType)
    })
  })

  //
  ;[
    ["name", "name"],
    [null, ""]
  ].forEach(([name, expectedPropName]) => {
    [true, false].forEach(hasOnChange => {
      it(`triggers ${
        hasOnChange ? "with" : "without"
      } an onChange when name=${String(name)}`, () => {
        const onChangeStub = sandbox.stub()
        const wrapper = render({
          name,
          onChange: hasOnChange ? onChangeStub : null
        })
        const ckWrapper = wrapper.find("CKEditor")

        const data = "some data"
        const editor = { getData: sandbox.stub().returns(data) }
        // @ts-expect-error CKEditor types are a work in progress
        ckWrapper.prop("onChange")(null, editor)
        if (hasOnChange) {
          sinon.assert.calledOnceWithExactly(onChangeStub, {
            target: { value: data, name: expectedPropName }
          })
        } else {
          expect(onChangeStub.called).toBe(false)
        }
      })
    })
  })
})
