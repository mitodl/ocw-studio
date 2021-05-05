import React from "react"

import { Website } from "../types/websites"

const WebsiteContext = React.createContext<Website | null>(null)
export default WebsiteContext
