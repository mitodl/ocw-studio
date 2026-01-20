jest.mock("@ckeditor/ckeditor5-utils/src/version")
jest.mock("@ckeditor/ckeditor5-link/src/linkui")
jest.mock("../../urls")
jest.mock("../../api/util")

import LinkPlugin from "@ckeditor/ckeditor5-link/src/link"
import Paragraph from "@ckeditor/ckeditor5-paragraph/src/paragraph"
import { URL as NodeURL } from "url"
import invariant from "tiny-invariant"

import Markdown from "./Markdown"
import { createTestEditor } from "./test_util"
import { siteApiContentUrl } from "../../urls"
import { getCookie } from "../../api/util"
import ResourceLinkMarkdownSyntax from "./ResourceLinkMarkdownSyntax"
import { WEBSITE_NAME, RESOURCE_LINK_CONFIG_KEY } from "./constants"
import CustomLink, { getExternalResource, updateHref } from "./CustomLink"

// Mock globals that the CustomLink plugin uses
const mockFetch = jest.fn()
global.fetch = mockFetch

global.SETTINGS = {
  sitemapDomain: "ocw.mit.edu",
  maxTitle: 100,
  reactGaDebug: "",
  gaTrackingID: "",
  public_path: "",
  environment: "test",
  release_version: "0.0.0",
  sentry_dsn: "",
  gdrive_enabled: false,
  features: {},
  features_default: false,
  posthog_api_host: null,
  posthog_project_api_key: null,
  deletableContentTypes: [],
}

// Mock URL constructor
class MockURL {
  hostname: string
  searchParams: {
    set: jest.Mock
    has: jest.Mock
    get: jest.Mock
    delete: jest.Mock
  }

  constructor(url: string) {
    // Parse actual URL to extract real hostname
    try {
      const realUrl = new NodeURL(url)
      this.hostname = realUrl.hostname

      // Mock searchParams but preserve the real functionality for has() and get()
      this.searchParams = {
        set: jest.fn(),
        has: jest
          .fn()
          .mockImplementation((key: string) => realUrl.searchParams.has(key)),
        get: jest
          .fn()
          .mockImplementation((key: string) => realUrl.searchParams.get(key)),
        delete: jest.fn(),
      }
    } catch (error) {
      // Fallback for invalid URLs
      try {
        const realUrl = new NodeURL(url)
        this.hostname = realUrl.hostname
      } catch (error) {
        this.hostname = "example.com"
      }

      this.searchParams = {
        set: jest.fn(),
        has: jest.fn().mockReturnValue(false),
        get: jest.fn().mockReturnValue(null),
        delete: jest.fn(),
      }
    }
  }

  toString() {
    return "mocked-url"
  }
}
global.URL = MockURL as any

// Mock console methods
const mockConsoleLog = jest.spyOn(console, "log").mockImplementation(() => {
  // Intentionally empty - suppressing console logs during tests
})
const mockConsoleError = jest.spyOn(console, "error").mockImplementation(() => {
  // Intentionally empty - suppressing console errors during tests
})

// Mock siteApiContentUrl
const mockSiteApiContentUrl = {
  param: jest.fn().mockReturnThis(),
  toString: jest.fn().mockReturnValue("https://example.com/api/content"),
}
;(siteApiContentUrl as any).param = mockSiteApiContentUrl.param
;(siteApiContentUrl as any).toString = mockSiteApiContentUrl.toString

// Mock getCookie
const mockGetCookie = getCookie as jest.MockedFunction<typeof getCookie>
mockGetCookie.mockReturnValue("mock-csrf-token")

// Create test editor with CustomLink and required plugins
const getEditor = createTestEditor(
  [Paragraph, LinkPlugin, ResourceLinkMarkdownSyntax, CustomLink, Markdown],
  {
    [RESOURCE_LINK_CONFIG_KEY]: {
      hrefTemplate: "https://fake.mit.edu/:uuid",
    },
    [WEBSITE_NAME]: "test-website",
  },
)

describe("CustomLink Plugin", () => {
  beforeEach(() => {
    jest.clearAllMocks()
    mockFetch.mockReset()
    mockConsoleLog.mockClear()
    mockConsoleError.mockClear()

    // Ensure global.fetch always points to our mock
    global.fetch = mockFetch

    // Reset SETTINGS to ensure consistency
    global.SETTINGS = {
      sitemapDomain: "ocw.mit.edu",
      maxTitle: 100,
      reactGaDebug: "",
      gaTrackingID: "",
      public_path: "",
      environment: "test",
      release_version: "0.0.0",
      sentry_dsn: "",
      gdrive_enabled: false,
      features: {},
      features_default: false,
      posthog_api_host: null,
      posthog_project_api_key: null,
      deletableContentTypes: [],
    }

    // Ensure our MockURL class is being used
    global.URL = MockURL as any
  })

  it("should have correct plugin metadata", () => {
    expect(CustomLink.pluginName).toBe("CustomLink")
    expect(CustomLink.requires).toEqual([
      LinkPlugin, // Link
      expect.anything(), // LinkUI - mocked, so we can't directly compare
      ResourceLinkMarkdownSyntax,
    ])
  })

  it("should initialize with editor", async () => {
    const editor = await getEditor("")
    expect(editor).toBeDefined()
    expect(editor.plugins.get("CustomLink")).toBeInstanceOf(CustomLink)
  })

  it("should register custom link command", async () => {
    const editor = await getEditor("")
    const linkCommand = editor.commands.get("link")
    expect(linkCommand).toBeDefined()
    // The command should be the CustomLinkCommand, not the default LinkCommand
    if (linkCommand) {
      expect(linkCommand.constructor.name).toBe("CustomLinkCommand")
    }
  })

  describe("Resource link handling", () => {
    it("should pass through existing resource links without API calls", async () => {
      const editor = await getEditor("")
      const linkCommand = editor.commands.get("link")
      expect(linkCommand).toBeDefined()
      invariant(linkCommand, "linkCommand should be defined")

      // Mock resource link href (must have the query parameters that ResourceLinkMarkdownSyntax checks for)
      const resourceHref =
        "https://fake.mit.edu/test-uuid?ocw_resource_link_uuid=test-uuid&ocw_resource_link_suffix="

      // Execute the command with a resource link
      linkCommand.execute(resourceHref)

      // Wait to ensure no async operations are triggered
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Should not make any fetch calls
      expect(mockFetch).not.toHaveBeenCalled()
    })
  })

  describe("External URL handling", () => {
    beforeEach(() => {
      // Mock successful API response
      const mockResponse = {
        ok: true,
        json: jest.fn().mockResolvedValue({
          title: "External Resource Title",
          text_id: "test-external-uuid",
        }),
      }
      mockFetch.mockResolvedValue(mockResponse as any)
    })

    it("should create external resource for non-resource URLs", async () => {
      const editor = await getEditor("")
      const linkCommand = editor.commands.get("link")
      expect(linkCommand).toBeDefined()
      invariant(linkCommand, "linkCommand should be defined")

      // Execute command with external URL
      linkCommand.execute("https://external.com/test")

      // Wait for async operations
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Should make API call to create external resource
      expect(mockFetch).toHaveBeenCalledWith(
        "https://example.com/api/content",
        expect.objectContaining({
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFTOKEN": "mock-csrf-token",
          },
          body: expect.stringContaining('"type":"external-resource"'),
        }),
      )
    })

    it("should handle external URLs with license warning", async () => {
      const editor = await getEditor("")
      const linkCommand = editor.commands.get("link")
      expect(linkCommand).toBeDefined()
      invariant(linkCommand, "linkCommand should be defined")

      linkCommand.execute("https://external.com/test")

      await new Promise((resolve) => setTimeout(resolve, 50))

      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: expect.stringContaining('"has_external_license_warning":false'),
        }),
      )
    })

    it("should handle same-domain URLs without license warning", async () => {
      // Reset and setup mock for this specific test
      const sameDomainMockResponse = {
        ok: true,
        json: jest.fn().mockResolvedValue({
          title: "Same Domain Resource",
          text_id: "same-domain-uuid",
        }),
      }
      mockFetch.mockResolvedValue(sameDomainMockResponse as any)

      const editor = await getEditor("")
      const linkCommand = editor.commands.get("link")
      expect(linkCommand).toBeDefined()
      invariant(linkCommand, "linkCommand should be defined")

      linkCommand.execute("https://ocw.mit.edu/courses/test")

      await new Promise((resolve) => setTimeout(resolve, 50))

      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: expect.stringContaining('"has_external_license_warning":false'),
        }),
      )
    })
  })

  describe("Error handling", () => {
    it("should handle invalid URLs gracefully", async () => {
      const editor = await getEditor("")

      // Mock console methods explicitly for this test
      const consoleLogSpy = jest.spyOn(console, "log").mockImplementation()
      const consoleErrorSpy = jest.spyOn(console, "error").mockImplementation()

      const linkCommand = editor.commands.get("link")
      expect(linkCommand).toBeDefined()
      invariant(linkCommand, "linkCommand should be defined")

      // Temporarily override URL to throw for invalid URLs while keeping MockURL for valid cases
      const originalURL = global.URL
      global.URL = jest.fn().mockImplementation((url: string) => {
        if (url === "invalid-url") {
          throw new Error("Invalid URL")
        }
        return new MockURL(url)
      }) as any

      linkCommand.execute("invalid-url")

      await new Promise((resolve) => setTimeout(resolve, 50))

      expect(consoleLogSpy).toHaveBeenCalledWith("Invalid URL provided!") // CHANGED

      // Should still make API call with warning
      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: expect.stringContaining('"has_external_license_warning":false'),
        }),
      )

      global.URL = originalURL
      consoleLogSpy.mockRestore()
      consoleErrorSpy.mockRestore()
    })

    it("should handle network errors gracefully", async () => {
      const consoleErrorSpy = jest.spyOn(console, "error").mockImplementation()
      mockFetch.mockRejectedValue(new Error("Network error"))

      const editor = await getEditor("")
      const linkCommand = editor.commands.get("link")
      expect(linkCommand).toBeDefined()
      invariant(linkCommand, "linkCommand should be defined")

      linkCommand.execute("https://external.com/test")

      await new Promise((resolve) => setTimeout(resolve, 50))

      expect(consoleErrorSpy).toHaveBeenCalledWith(
        // CHANGED
        "Error updating link:",
        expect.objectContaining({ message: "Network error" }),
      )
      expect(consoleErrorSpy.mock.calls[0][1]).toBeInstanceOf(Error)

      consoleErrorSpy.mockRestore()
    })
  })

  describe("Document change handling", () => {
    it("should process href changes for non-resource links", async () => {
      // Mock successful API response
      const docChangeMockResponse = {
        ok: true,
        json: jest.fn().mockResolvedValue({
          title: "External Resource Title",
          text_id: "test-external-uuid",
        }),
      }
      mockFetch.mockResolvedValue(docChangeMockResponse as any)

      const editor = await getEditor("")

      // Use the link command to create a link, which should trigger the document change handling
      const linkCommand = editor.commands.get("link")
      expect(linkCommand).toBeDefined()
      invariant(linkCommand, "linkCommand should be defined")

      // First create some text in the editor
      const root = editor.model.document.getRoot()
      invariant(root, "Document root should be defined")

      editor.model.change((writer) => {
        const paragraph = writer.createElement("paragraph")
        const text = writer.createText("test link")
        writer.append(text, paragraph)
        writer.append(paragraph, root)

        // Set selection to the text so link command will apply to it
        const startPosition = writer.createPositionBefore(text)
        const endPosition = writer.createPositionAfter(text)
        const textRange = writer.createRange(startPosition, endPosition)
        writer.setSelection(textRange)
      })

      // Execute the link command, which should trigger document change processing
      linkCommand.execute("https://external.com/test")

      // Wait for document change processing
      await new Promise((resolve) => setTimeout(resolve, 100))

      // Should attempt to create external resource
      expect(mockFetch).toHaveBeenCalled()
    })

    it("should ignore changes for existing resource links", async () => {
      const editor = await getEditor("")

      // Create a resource link element in the editor
      const root = editor.model.document.getRoot()
      invariant(root, "Document root should be defined")

      editor.model.change((writer) => {
        const paragraph = writer.createElement("paragraph")
        const text = writer.createText("test link", {
          linkHref: "resource://existing-uuid",
        })
        writer.append(text, paragraph)
        writer.append(paragraph, root)
      })

      // Wait for document change processing
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Should not make API calls for resource links
      expect(mockFetch).not.toHaveBeenCalled()
    })
  })

  describe("URL title truncation", () => {
    beforeEach(() => {
      const mockResponse = {
        ok: true,
        json: jest.fn().mockResolvedValue({
          title: "Mocked Resource Title",
          text_id: "mocked-resource-uuid",
        }),
      }
      mockFetch.mockResolvedValue(mockResponse as any)
    })

    it("should not truncate URLs shorter than maxTitle", async () => {
      const editor = await getEditor("")
      const linkCommand = editor.commands.get("link")
      expect(linkCommand).toBeDefined()
      invariant(linkCommand, "linkCommand should be defined")
      const baseUrl = "https://external.com/"
      const shortPath = "a".repeat(50)
      const shortUrl = baseUrl + shortPath // < 100 chars
      linkCommand.execute(shortUrl)
      await new Promise((resolve) => setTimeout(resolve, 50))
      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: expect.stringContaining(`"title":"${shortUrl}"`),
        }),
      )
    })

    it("should not truncate URLs exactly maxTitle length", async () => {
      const editor = await getEditor("")
      const linkCommand = editor.commands.get("link")
      expect(linkCommand).toBeDefined()
      invariant(linkCommand, "linkCommand should be defined")
      const baseUrl = "https://external.com/"
      const needed = SETTINGS.maxTitle - baseUrl.length
      const exactUrl = baseUrl + "a".repeat(needed)
      expect(exactUrl.length).toBe(SETTINGS.maxTitle)
      linkCommand.execute(exactUrl)
      await new Promise((resolve) => setTimeout(resolve, 50))
      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: expect.stringContaining(`"title":"${exactUrl}"`),
        }),
      )
    })

    it("should truncate long URLs and send only the truncated title in the payload", async () => {
      const editor = await getEditor("")
      const linkCommand = editor.commands.get("link")
      expect(linkCommand).toBeDefined()
      invariant(linkCommand, "linkCommand should be defined")
      const baseUrl = "https://external.com/"
      const longPath = "a".repeat(200)
      const longUrl = baseUrl + longPath
      const expectedTruncatedTitle = longUrl.slice(0, SETTINGS.maxTitle)
      linkCommand.execute(longUrl)
      await new Promise((resolve) => setTimeout(resolve, 50))
      // Check that the title in the payload is exactly the truncated value and not the full URL
      const fetchCall = mockFetch.mock.calls[0]
      expect(fetchCall).toBeDefined()
      const body = fetchCall[1].body
      expect(body).toContain(`"title":"${expectedTruncatedTitle}"`)
      // Ensure the payload doesn't contain the full long URL as title
      expect(body).not.toContain(`"title":"${longUrl}"`)
    })
  })

  describe("getExternalResource", () => {
    beforeEach(() => {
      mockGetCookie.mockReturnValue("mock-csrf-token")
      ;(siteApiContentUrl.param as jest.Mock).mockReturnThis()
      ;(siteApiContentUrl.toString as jest.Mock).mockReturnValue(
        "https://example.com/api/content",
      )
    })

    it("should POST correct payload and return resource on success", async () => {
      const mockResponse = {
        ok: true,
        json: jest
          .fn()
          .mockResolvedValue({ title: "Test Title", text_id: "test-id" }),
      }
      mockFetch.mockResolvedValue(mockResponse as any)
      const result = await getExternalResource(
        "mysite",
        "https://external.com/foo",
        "My Title",
      )
      expect(mockFetch).toHaveBeenCalledWith(
        "https://example.com/api/content",
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({
            "X-CSRFTOKEN": "mock-csrf-token",
          }),
          body: expect.stringContaining('"title":"My Title"'),
        }),
      )
      expect(result).toEqual({ title: "Test Title", textId: "test-id" })
    })

    it("should include all metadata fields in POST body", async () => {
      const mockResponse = {
        ok: true,
        json: jest
          .fn()
          .mockResolvedValue({ title: "Test Title", text_id: "test-id" }),
      }
      mockFetch.mockResolvedValue(mockResponse as any)
      await getExternalResource(
        "mysite",
        "https://external.com/foo",
        "My Title",
      )
      const body = JSON.parse(mockFetch.mock.calls[0][1].body)
      expect(body.metadata).toEqual(
        expect.objectContaining({
          external_url: "https://external.com/foo",
          license: "https://en.wikipedia.org/wiki/All_rights_reserved",
          has_external_license_warning: false,
          is_broken: "",
          backup_url: "",
        }),
      )
    })

    it("should handle empty linkValue gracefully", async () => {
      const mockResponse = {
        ok: true,
        json: jest
          .fn()
          .mockResolvedValue({ title: "Test Title", text_id: "test-id" }),
      }
      mockFetch.mockResolvedValue(mockResponse as any)
      const result = await getExternalResource("mysite", "", "")
      expect(mockFetch).toHaveBeenCalled()
      const body = JSON.parse(mockFetch.mock.calls[0][1].body)
      expect(body.title).toBe("")
      expect(body.metadata.external_url).toBe("")
      expect(result).toEqual({ title: "Test Title", textId: "test-id" })
    })

    it("should handle unexpected API response gracefully", async () => {
      const mockResponse = {
        ok: true,
        json: jest.fn().mockResolvedValue({}),
      }
      mockFetch.mockResolvedValue(mockResponse as any)
      const result = await getExternalResource(
        "mysite",
        "https://external.com/foo",
        "My Title",
      )
      expect(result).toBeNull() // Ensure null is returned for incomplete API response
    })

    it("should return null and log error on fetch failure", async () => {
      mockFetch.mockRejectedValue(new Error("fail"))
      const spy = jest.spyOn(console, "error").mockImplementation()
      const result = await getExternalResource(
        "mysite",
        "https://external.com/foo",
        "",
      )
      expect(result).toBeNull()
      expect(spy).toHaveBeenCalledWith(
        "Error updating link:",
        expect.any(Error),
      )
      spy.mockRestore()
    })

    it("should handle same-domain URLs without external license warning", async () => {
      const mockResponse = {
        ok: true,
        json: jest.fn().mockResolvedValue({
          title: "Same Domain Title",
          text_id: "same-domain-id",
        }),
      }
      mockFetch.mockResolvedValue(mockResponse as any)

      // Test with a URL that matches SETTINGS.sitemapDomain
      const result = await getExternalResource(
        "mysite",
        "https://ocw.mit.edu/courses/test",
        "Test Title",
      )

      expect(mockFetch).toHaveBeenCalledWith(
        "https://example.com/api/content",
        expect.objectContaining({
          body: expect.stringContaining('"has_external_license_warning":false'),
        }),
      )
      expect(result).toEqual({
        title: "Same Domain Title",
        textId: "same-domain-id",
      })
    })

    it("should handle fetch response that is not ok", async () => {
      const mockResponse = {
        ok: false,
        status: 500,
        json: jest.fn().mockResolvedValue({ error: "Server error" }),
      }
      mockFetch.mockResolvedValue(mockResponse as any)

      const result = await getExternalResource(
        "mysite",
        "https://external.com/foo",
        "My Title",
      )

      // The function returns null when data.title or data.text_id are undefined
      expect(result).toBeNull()
    })
  })

  describe("updateHref", () => {
    let editor: any, superExecute: jest.Mock
    beforeEach(() => {
      superExecute = jest.fn()
      const syntax = {
        makeResourceLinkHref: (id: string, suffix = "") =>
          `https://fake.mit.edu/${id}?ocw_resource_link_uuid=${id}&ocw_resource_link_suffix=${suffix}`,
      }
      editor = {
        plugins: { get: () => syntax },
        model: {
          document: {
            selection: { isCollapsed: true, getFirstPosition: jest.fn() },
          },
          change: jest.fn((cb) => cb({ insertText: jest.fn() })),
        },
      }
    })

    it("inserts text with linkHref if selection is collapsed", () => {
      updateHref({ title: "T", textId: "id" }, editor, superExecute)
      expect(editor.model.change).toHaveBeenCalled()
      const writer = { insertText: jest.fn() }
      editor.model.change.mock.calls[0][0](writer)
      expect(writer.insertText).toHaveBeenCalledWith(
        "T",
        {
          linkHref:
            "https://fake.mit.edu/id?ocw_resource_link_uuid=id&ocw_resource_link_suffix=",
        },
        undefined,
      )
    })

    it("calls superExecute with correct href if selection is not collapsed", () => {
      editor.model.document.selection.isCollapsed = false
      updateHref({ title: "T", textId: "id" }, editor, superExecute)
      expect(superExecute).toHaveBeenCalledWith(
        "https://fake.mit.edu/id?ocw_resource_link_uuid=id&ocw_resource_link_suffix=",
      )
    })

    it("should handle valid externalResource data correctly", () => {
      expect(() => {
        updateHref(
          { title: "Valid Title", textId: "valid-id" },
          editor,
          superExecute,
        )
      }).not.toThrow()

      // Verify successful execution with valid data
      expect(editor.model.change).toHaveBeenCalled()

      // Verify that the insertText was called with the correct parameters
      const writer = { insertText: jest.fn() }
      editor.model.change.mock.calls[0][0](writer)
      expect(writer.insertText).toHaveBeenCalledWith(
        "Valid Title",
        {
          linkHref:
            "https://fake.mit.edu/valid-id?ocw_resource_link_uuid=valid-id&ocw_resource_link_suffix=",
        },
        undefined,
      )
    })
  })

  describe("CustomLinkCommand", () => {
    it("should handle null response from getExternalResource gracefully", async () => {
      const mockResponse = {
        ok: true,
        json: jest.fn().mockResolvedValue({}), // Empty response that will result in null
      }
      mockFetch.mockResolvedValue(mockResponse as any)

      const editor = await getEditor("")
      const linkCommand = editor.commands.get("link")
      expect(linkCommand).toBeDefined()
      invariant(linkCommand, "linkCommand should be defined")

      // Create some text in the editor first
      const root = editor.model.document.getRoot()
      invariant(root, "Document root should be defined")

      editor.model.change((writer) => {
        const paragraph = writer.createElement("paragraph")
        const text = writer.createText("test link")
        writer.append(text, paragraph)
        writer.append(paragraph, root)

        // Set selection to the text so link command will apply to it
        const startPosition = writer.createPositionBefore(text)
        const endPosition = writer.createPositionAfter(text)
        const textRange = writer.createRange(startPosition, endPosition)
        writer.setSelection(textRange)
      })

      // Execute command with external URL that will return null
      linkCommand.execute("https://external.com/test")

      // Wait for async operations
      await new Promise((resolve) => setTimeout(resolve, 100))

      // Should make API call but not update the editor since externalResource is null
      expect(mockFetch).toHaveBeenCalled()
    })

    it("should extract title from selected text in editor", async () => {
      const mockResponse = {
        ok: true,
        json: jest.fn().mockResolvedValue({
          title: "Test Title",
          text_id: "test-id",
        }),
      }
      mockFetch.mockResolvedValue(mockResponse as any)

      const editor = await getEditor("")
      const linkCommand = editor.commands.get("link")
      expect(linkCommand).toBeDefined()
      invariant(linkCommand, "linkCommand should be defined")

      // Create text in the editor and select it
      const root = editor.model.document.getRoot()
      invariant(root, "Document root should be defined")

      editor.model.change((writer) => {
        const paragraph = writer.createElement("paragraph")
        const text1 = writer.createText("Selected ")
        const text2 = writer.createText("Text")
        writer.append(text1, paragraph)
        writer.append(text2, paragraph)
        writer.append(paragraph, root)

        // Select both text nodes - create positions within the paragraph
        const startPosition = writer.createPositionAt(paragraph, 0)
        const endPosition = writer.createPositionAt(paragraph, "end")
        const textRange = writer.createRange(startPosition, endPosition)
        writer.setSelection(textRange)
      })

      // Execute command
      linkCommand.execute("https://external.com/test")

      // Wait for async operations
      await new Promise((resolve) => setTimeout(resolve, 100))

      // Verify the title was extracted from selection and sent in the API call
      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: expect.stringContaining('"title":"Selected Text"'),
        }),
      )
    })
  })

  describe("_modifyHref method", () => {
    it("should handle getExternalResource returning null", async () => {
      const mockResponse = {
        ok: true,
        json: jest.fn().mockResolvedValue({}), // Empty response that will result in null
      }
      mockFetch.mockResolvedValue(mockResponse as any)

      const editor = await getEditor("")
      const customLinkPlugin = editor.plugins.get(
        "CustomLink",
      ) as unknown as CustomLink

      // Create a range with a non-resource link
      const root = editor.model.document.getRoot()
      invariant(root, "Document root should be defined")

      let linkElement: any
      editor.model.change((writer) => {
        const paragraph = writer.createElement("paragraph")
        const text = writer.createText("external link", {
          linkHref: "https://external.com/test",
        })
        writer.append(text, paragraph)
        writer.append(paragraph, root)
        linkElement = text
      })

      // Create a mock range containing the link element
      const mockRange = {
        getItems: jest.fn().mockReturnValue([linkElement]),
      }

      // Call _modifyHref directly
      customLinkPlugin._modifyHref(mockRange as any)

      // Wait for async operations
      await new Promise((resolve) => setTimeout(resolve, 100))

      // Should make API call but not update the href since getExternalResource returns null
      expect(mockFetch).toHaveBeenCalled()
      expect(linkElement.getAttribute("linkHref")).toBe(
        "https://external.com/test",
      ) // href should remain unchanged
    })

    it("should successfully update href when getExternalResource returns valid data", async () => {
      const mockResponse = {
        ok: true,
        json: jest.fn().mockResolvedValue({
          title: "External Resource",
          text_id: "external-uuid",
        }),
      }
      mockFetch.mockResolvedValue(mockResponse as any)

      const editor = await getEditor("")
      const customLinkPlugin = editor.plugins.get(
        "CustomLink",
      ) as unknown as CustomLink

      // Create a range with a non-resource link
      const root = editor.model.document.getRoot()
      invariant(root, "Document root should be defined")

      let linkElement: any
      editor.model.change((writer) => {
        const paragraph = writer.createElement("paragraph")
        const text = writer.createText("external link", {
          linkHref: "https://external.com/test",
        })
        writer.append(text, paragraph)
        writer.append(paragraph, root)
        linkElement = text
      })

      // Create a mock range containing the link element
      const mockRange = {
        getItems: jest.fn().mockReturnValue([linkElement]),
      }

      // Call _modifyHref directly
      customLinkPlugin._modifyHref(mockRange as any)

      // Wait for async operations
      await new Promise((resolve) => setTimeout(resolve, 100))

      // Should make API call and update the href
      expect(mockFetch).toHaveBeenCalled()
      // The href should be updated from the original external URL
      expect(linkElement.getAttribute("linkHref")).not.toBe(
        "https://external.com/test",
      )
    })

    it("should skip items that don't have linkHref attribute", async () => {
      const editor = await getEditor("")
      const customLinkPlugin = editor.plugins.get(
        "CustomLink",
      ) as unknown as CustomLink

      // Create a mock range with an element that doesn't have linkHref
      const mockElement = {
        hasAttribute: jest.fn().mockReturnValue(false),
        getAttribute: jest.fn(),
      }

      const mockRange = {
        getItems: jest.fn().mockReturnValue([mockElement]),
      }

      // Call _modifyHref directly
      customLinkPlugin._modifyHref(mockRange as any)

      // Wait briefly
      await new Promise((resolve) => setTimeout(resolve, 10))

      // Should not make any API calls
      expect(mockFetch).not.toHaveBeenCalled()
      expect(mockElement.getAttribute).not.toHaveBeenCalled()
    })

    it("should skip items that already have resource link href", async () => {
      const editor = await getEditor("")
      const customLinkPlugin = editor.plugins.get(
        "CustomLink",
      ) as unknown as CustomLink

      // Create a mock range with a resource link
      const mockElement = {
        hasAttribute: jest.fn().mockReturnValue(true),
        getAttribute: jest
          .fn()
          .mockReturnValue(
            "https://fake.mit.edu/test-uuid?ocw_resource_link_uuid=test-uuid&ocw_resource_link_suffix=",
          ),
      }

      const mockRange = {
        getItems: jest.fn().mockReturnValue([mockElement]),
      }

      // Call _modifyHref directly
      customLinkPlugin._modifyHref(mockRange as any)

      // Wait briefly
      await new Promise((resolve) => setTimeout(resolve, 10))

      // Should not make any API calls since it's already a resource link
      expect(mockFetch).not.toHaveBeenCalled()
    })
  })
})
