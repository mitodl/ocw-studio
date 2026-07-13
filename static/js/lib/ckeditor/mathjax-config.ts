/**
 * MathJax configuration.
 *
 * This module MUST be imported before mathjax/tex-svg.js — MathJax reads
 * window.MathJax at initialisation time and merges it with defaults.
 */

declare global {
  interface Window {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    MathJax: any
  }
}

window.MathJax = {
  tex: {
    equationNumbers: {
      autoNumber: "AMS",
    },
  },
  svg: {
    displayAlign: "left",
    displayIndent: "2em",
  },
  startup: {
    ready() {
      window.MathJax.startup.defaultReady()
      // ckeditor5-math only supports MathJax v2/v3 API detection. It checks
      // version.startsWith('3') to use the v3 path (tex2svgPromise), and falls
      // back to the v2 Hub.Queue API otherwise. MathJax 4 exposes the same
      // tex2svgPromise API as v3, so we expose a v3-compatible version string.
      window.MathJax._version = window.MathJax.version
      window.MathJax.version = "3.99.0"
    },
  },
}

export {}
