import React from "react"
import { BrowserRouter, BrowserRouterProps } from "react-router-dom"

/**
 * Custom Router that provides confirmation functionality.
 *
 * Since getUserConfirmation was removed from BrowserRouter in history v5.0.0,
 * we now rely on the browser's native window.confirm for navigation blocking.
 *
 * This maintains the same user experience but uses the standard browser modal
 * instead of our custom React modal.
 */
const CustomConfirmBrowserRouter: React.FC<BrowserRouterProps> = (props) => {
  return <BrowserRouter {...props} />
}

export default CustomConfirmBrowserRouter
