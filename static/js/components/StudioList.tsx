import React, { useCallback, useState } from "react"
import { Link, useLocation } from "react-router-dom"
import OutsideClickHandler from "react-outside-click-handler"
import classNames from "classnames"

import Card from "./Card"

interface ListProps {
  children: React.ReactNode
}

/**
 * A list component which basically just consists of a
 * 'bare' list (i.e. no list styling). Use with the
 * `StudioListItem` component for consistent list styling
 * across the site!
 */
export function StudioList(props: ListProps): JSX.Element {
  const { children } = props

  return <ul className="studio-list">{children}</ul>
}

type MenuOption = [string, (event: React.MouseEvent<HTMLButtonElement>) => void]

export interface ListItemProps {
  title: string
  subtitle: string
  to?: string
  onClick?: (e: React.MouseEvent<HTMLLIElement>) => void
  children?: React.ReactNode
  menuOptions?: MenuOption[]
}

/**
 * A list item component for various listing pages which is somewhat
 * controlled. You can pass a title and a subtitle, and menu options
 * for an optional dropdown menu.
 *
 * If you pass `children` they will be rendered at the right side of
 * the component, to the left of the dropdown menu.
 */
export function StudioListItem(props: ListItemProps): JSX.Element {
  const { title, subtitle, onClick, to, children, menuOptions } = props

  const [menuOpen, setMenuOpen] = useState(false)

  const location = useLocation()

  const openMenu = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault()
      setMenuOpen(true)
    },
    [setMenuOpen]
  )

  const closeMenu = useCallback(
    (e: MouseEvent) => {
      if (e) {
        e.preventDefault()
      }
      setMenuOpen(false)
    },
    [setMenuOpen]
  )

  return (
    <li
      className={classNames({
        "my-3":          true,
        "hover-pointer": Boolean(onClick)
      })}
      onClick={onClick}
    >
      <Card>
        <div className="d-flex flex-row align-items-center justify-content-between">
          <div className="d-flex flex-column flex-grow-1">
            {to ? (
              <Link className="title" to={{ ...location, pathname: to }}>
                {title}
              </Link>
            ) : (
              <div className="title">{title}</div>
            )}
            <div className="subtitle">{subtitle}</div>
          </div>
          <div>
            {children}
            {menuOptions && menuOptions.length > 0 ? (
              <div className="dropdown">
                <button
                  className="transparent-button"
                  type="button"
                  id="dropdownMenuButton"
                  onClick={openMenu}
                  data-toggle="dropdown"
                  aria-haspopup="true"
                  aria-expanded={menuOpen}
                >
                  <i className="material-icons">more_vert</i>
                </button>
                {menuOpen ? (
                  <OutsideClickHandler onOutsideClick={closeMenu}>
                    <div
                      className="dropdown-menu right show"
                      aria-labelledby="dropdownMenuButton"
                    >
                      {menuOptions.map(([label, clickHandler], idx) => (
                        <button
                          onClick={clickHandler}
                          className="dropdown-item"
                          type="button"
                          key={idx}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  </OutsideClickHandler>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>
      </Card>
    </li>
  )
}
