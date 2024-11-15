const { TextEncoder, TextDecoder } = require("util")
const { ReadableStream, TransformStream } = require("stream/web")

global.TextEncoder = TextEncoder
global.TextDecoder = TextDecoder

global.ReadableStream = ReadableStream
global.TransformStream = TransformStream
