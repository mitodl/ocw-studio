import React, { CSSProperties } from "react"

const spinnerStyle: CSSProperties = {
  width:  "100%",
  height: "100%"
}

const spinnerContainerStyle: CSSProperties = {
  position: "absolute",

  /**
   * Ensure the spinner container has aspect ratio 1:1.
   * This property is "weak" and will be ignored if anything else sets the
   * dimensions of the element, so ensure both width and height are set.
   */
  aspectRatio: "1 / 1",
  width:       "clamp(2rem, 3%, 4rem)",
  height:      "auto",

  /**
   * Position the spinner's container relative to its parent. Use transform so
   * that we are positioning its center, not its corner.
   *
   * (Uisng transform directly on the spinner messes things up. Presumably
   * bootstrap is already animating it using transforms.)
   */
  top:       "25%",
  left:      "50%",
  transform: "translate(-50%, -50%)"
}

export default function Spinner() {
  return (
    <div style={spinnerContainerStyle}>
      <div
        className="spinner-border dark-gray"
        style={spinnerStyle}
        role="status"
      >
        <span className="sr-only">Loading...</span>
      </div>
    </div>
  )
}
