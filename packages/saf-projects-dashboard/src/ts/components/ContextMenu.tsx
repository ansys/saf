import React, { useState, useRef, useEffect } from "react";
import { icons } from "../utils/icons";
import "../styles/ContextMenu.css";

export type MenuItem = {
  label: string;
  icon: string;
  onClick: () => void;
  className?: string;
};

type ContextMenuProps = {
  items: MenuItem[];
};

const ContextMenu: React.FC<ContextMenuProps> = ({ items }) => {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;

    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [open]);

  return (
    <div className="context-menu" ref={menuRef}>
      <button
        className="context-menu-trigger"
        onClick={(e) => {
          e.stopPropagation();
          setOpen((prev) => !prev);
        }}
        aria-label="More actions"
        aria-expanded={open}
        aria-haspopup="menu"
      >
        <span
          className="awc-icon"
          dangerouslySetInnerHTML={{ __html: icons.more }}
        />
      </button>
      {open && (
        <ul className="context-menu-dropdown" role="menu">
          {items.map((item) => (
            <li key={item.label} role="none">
              <button
                role="menuitem"
                className={`context-menu-item ${item.className ?? ""}`}
                onClick={(e) => {
                  e.stopPropagation();
                  item.onClick();
                  setOpen(false);
                }}
              >
                <span
                  className="awc-icon"
                  dangerouslySetInnerHTML={{ __html: item.icon }}
                />
                {item.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default ContextMenu;
