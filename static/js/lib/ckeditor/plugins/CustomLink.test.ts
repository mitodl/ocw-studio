jest.mock("@ckeditor/ckeditor5-utils/src/version")
jest.mock("@ckeditor/ckeditor5-link/src/linkui")
jest.mock("../../urls")
jest.mock("../../api/util")

import LinkPlugin from "@ckeditor/ckeditor5-link/src/link"
import Paragraph from "@ckeditor/ckeditor5-paragraph/src/paragraph"
import { URL as NodeURL } from "url"

import Markdown from "./Markdown"
import { createTestEditor } from "./test_util"
import { siteApiContentUrl } from "../../urls"
import { getCookie } from "../../api/util"
import ResourceLinkMarkdownSyntax from "./ResourceLinkMarkdownSyntax"
import { WEBSITE_NAME, RESOURCE_LINK_CONFIG_KEY } from "./constants"
import CustomLink from "./CustomLink"

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
      if (url.includes("external.com")) {
        this.hostname = "external.com"
      } else if (url.includes("ocw.mit.edu")) {
        this.hostname = "ocw.mit.edu"
      } else if (url.includes("fake.mit.edu")) {
        this.hostname = "fake.mit.edu"
      } else {
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
const mockConsoleLog = jest.spyOn(console, "log").mockImplementation()
const mockConsoleError = jest.spyOn(console, "error").mockImplementation()

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
      expect.anything(), // Link
      expect.anything(), // LinkUI
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
    beforeEach(() => {
      // Reset mock fetch for these tests
      mockFetch.mockReset()
    })

    it("should pass through existing resource links without API calls", async () => {
      const editor = await getEditor("")
      const linkCommand = editor.commands.get("link")
      expect(linkCommand).toBeDefined()

      if (!linkCommand) return

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
      // Reset and setup mock fetch for these tests
      mockFetch.mockReset()

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
      // Setup mock fetch directly in the test
      mockFetch.mockReset()
      const mockResponse = {
        ok: true,
        json: jest.fn().mockResolvedValue({
          title: "External Resource Title",
          text_id: "test-external-uuid",
        }),
      }
      mockFetch.mockResolvedValue(mockResponse as any)

      const editor = await getEditor("")
      const linkCommand = editor.commands.get("link")
      expect(linkCommand).toBeDefined()

      if (!linkCommand) return

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

      if (!linkCommand) return

      linkCommand.execute("https://external.com/test")

      await new Promise((resolve) => setTimeout(resolve, 50))

      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: expect.stringContaining('"has_external_license_warning":true'),
        }),
      )
    })

    it("should handle same-domain URLs without license warning", async () => {
      // Reset and setup mock for this specific test
      mockFetch.mockReset()
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

      if (!linkCommand) return

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
      // Reset and setup mock fetch for this test
      mockFetch.mockReset()
      const invalidUrlMockResponse = {
        ok: true,
        json: jest.fn().mockResolvedValue({
          title: "Resource Title",
          text_id: "resource-uuid",
        }),
      }
      mockFetch.mockResolvedValue(invalidUrlMockResponse as any)

      const editor = await getEditor("")

      // Mock console methods explicitly for this test
      mockConsoleLog.mockImplementation()
      mockConsoleError.mockImplementation()

      const linkCommand = editor.commands.get("link")
      expect(linkCommand).toBeDefined()

      if (!linkCommand) return

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

      expect(mockConsoleLog).toHaveBeenCalledWith("Invalid URL provided!")

      // Should still make API call with warning
      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: expect.stringContaining('"has_external_license_warning":true'),
        }),
      )

      global.URL = originalURL
    })

    it("should handle network errors gracefully", async () => {
      // Reset mock and setup to reject
      mockFetch.mockReset()

      // Mock console.error to capture the error without throwing
      const originalConsoleError = console.error
      let capturedError: any = null
      console.error = jest.fn((message: string, error: any) => {
        capturedError = { message, error }
      })

      mockFetch.mockRejectedValue(new Error("Network error"))

      const editor = await getEditor("")
      const linkCommand = editor.commands.get("link")
      expect(linkCommand).toBeDefined()

      if (!linkCommand) return

      linkCommand.execute("https://external.com/test")

      await new Promise((resolve) => setTimeout(resolve, 50))

      // Restore console.error
      console.error = originalConsoleError

      // Check that error was captured
      expect(capturedError).not.toBeNull()
      expect(capturedError.message).toBe("Error updating link:")
      expect(capturedError.error).toBeInstanceOf(Error)
      expect(capturedError.error.message).toBe("Network error")
    })
  })

  describe("Document change handling", () => {
    it("should process href changes for non-resource links", async () => {
      // Reset and setup mock fetch
      mockFetch.mockReset()

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

      if (!linkCommand) return

      // First create some text in the editor
      const root = editor.model.document.getRoot()
      if (!root) return

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
      // Reset mock fetch to ensure clean state
      mockFetch.mockReset()

      const editor = await getEditor("")

      // Create a resource link element in the editor
      const root = editor.model.document.getRoot()
      if (!root) return

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
    it("should truncate long URLs when used as title", async () => {
      // Reset and setup mock fetch
      mockFetch.mockReset()

      const editor = await getEditor("")
      const linkCommand = editor.commands.get("link")
      expect(linkCommand).toBeDefined()

      if (!linkCommand) return

      const truncationMockResponse = {
        ok: true,
        json: jest.fn().mockResolvedValue({
          title: "Resource Title",
          text_id: "resource-uuid",
        }),
      }
      mockFetch.mockResolvedValue(truncationMockResponse as any)

      // Create URL longer than SETTINGS.maxTitle (100 chars)
      const baseUrl = "https://external.com/"
      const longPath = "a".repeat(200)
      const longUrl = baseUrl + longPath

      // Expected truncated title should be first 100 chars of the full URL
      const expectedTruncatedTitle = longUrl.slice(0, SETTINGS.maxTitle)

      linkCommand.execute(longUrl)

      await new Promise((resolve) => setTimeout(resolve, 50))

      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: expect.stringContaining(`"title":"${expectedTruncatedTitle}"`),
        }),
      )
    })
  })
})
