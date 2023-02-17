import React, { useCallback, useState } from "react"
import { MaterialIcons } from "../types/common"
import { WebsiteDropdown } from "../types/websites"


export default function Dropdown(props: {
  websiteName: string
  dropdownBtnID: string
  materialIcon: MaterialIcons
  dropdownMenu: WebsiteDropdown[]
}): JSX.Element | null {
  const { websiteName, dropdownBtnID, materialIcon, dropdownMenu } = props

  const [menuOpen, setMenuOpen] = useState(false)

  const openMenu = useCallback(
    (e: React.MouseEvent) => {
      if (e) {
        e.preventDefault()
      }
      setMenuOpen(true)
    },
    [setMenuOpen]
  )

  const closeMenu = useCallback(
    (e: React.MouseEvent) => {
      if (e) {
        e.preventDefault()
      }
      setMenuOpen(false)
    },
    [setMenuOpen]
  )

  const dropdownMenuBtnOnClickHandler = useCallback(
    (e: React.MouseEvent, clickHandler: (...args: any[]) => void) => {
      if (e) {
        e.preventDefault()
      }
      clickHandler(websiteName)
      closeMenu(e)
    },
    [closeMenu, websiteName]
  )

  if (!dropdownMenu.length) {
    return null
  }

  return (
    <div className="dropdown">
      <button
        className="transparent-button"
        type="button"
        id={dropdownBtnID}
        onClick={menuOpen ? closeMenu : openMenu}
        data-toggle="dropdown"
        aria-haspopup="true"
        aria-expanded={menuOpen}
      >
        <i className="material-icons">{materialIcon}</i>
      </button>
      {menuOpen ? (
        <div className="dropdown-menu right show" aria-labelledby={dropdownBtnID}>
          {dropdownMenu.map((menu: WebsiteDropdown) => (
            <button
              onClick={e=>dropdownMenuBtnOnClickHandler(e, menu.clickHandler)}
              className="dropdown-item"
              type="button"
              key={menu.id}
            >
              {menu.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  )
}
