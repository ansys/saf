/**
 * OSS Icon Utility
 *
 * Imports SVG icons from the OSS assets bundle as inline strings.
 * Icons are embedded directly in the JS bundle for zero extra HTTP requests.
 *
 * Licenses:
 *  OSS icons are licensed under the Open Source MIT License, that
 *  are free:
 * - to share – to copy, distribute and transmit the work
 * - to remix – to adapt the work
 *
 * Under the following terms:
 *
 * - liability – the author doesn't provide any warranty and doesn't accepts any liability
 * - copyright notice – a copy of the license or copyright notice must be included with software
 * - share alike – If you remix, transform, or build upon the material, you can distribute your work under any license
 *
 * Usage:
 *   import { icons } from "../utils/icons";
 *   <span dangerouslySetInnerHTML={{ __html: icons.edit }} />
 */

// Action icons
import editSvg from "../assets/oss-icons/edit.svg";
import deleteSvg from "../assets/oss-icons/delete.svg";
import downloadSvg from "../assets/oss-icons/download.svg";
import addSvg from "../assets/oss-icons/add.svg";
import addGeometrySvg from "../assets/oss-icons/add.svg";
import closeSvg from "../assets/oss-icons/close.svg";
import restartSvg from "../assets/oss-icons/restart.svg";
import importSvg from "../assets/oss-icons/import.svg";
import searchSvg from "../assets/oss-icons/search.svg";

// Navigation / menu icons
import moreSvg from "../assets/oss-icons/more.svg";

// Status icons
import checkSvg from "../assets/oss-icons/check.svg";
import errorSvg from "../assets/oss-icons/error.svg";
import warningSvg from "../assets/oss-icons/warning.svg";
import infoOutlineSvg from "../assets/oss-icons/info-outline.svg";

// Favorite icons
import starSvg from "../assets/oss-icons/star.svg";
import starOutlineSvg from "../assets/oss-icons/star-outline.svg";

// View toggle icons
import viewListSvg from "../assets/oss-icons/view-list.svg";
import viewBlocksSvg from "../assets/oss-icons/view-blocks.svg";

// Theme toggle icons
import moonSvg from "../assets/oss-icons/moon.svg";
import sunSvg from "../assets/oss-icons/sun.svg";

// Object icons
import documentSvg from "../assets/oss-icons/document.svg";
import folderSvg from "../assets/oss-icons/folder.svg";
import projectSvg from "../assets/oss-icons/folder.svg";
import applicationSvg from "../assets/application.svg";
import filterSvg from "../assets/oss-icons/filter.svg";
import helpSvg from "../assets/oss-icons/help.svg";

// Access control icons
import lockSvg from "../assets/oss-icons/lock.svg";
import shareSvg from "../assets/oss-icons/share.svg";

export const icons = {
  // Actions
  edit: editSvg,
  delete: deleteSvg,
  download: downloadSvg,
  add: addSvg,
  addGeometry: addGeometrySvg,
  close: closeSvg,
  restart: restartSvg,
  import: importSvg,
  search: searchSvg,

  // Status
  check: checkSvg,
  error: errorSvg,
  warning: warningSvg,
  infoOutline: infoOutlineSvg,

  // Navigation / menu
  more: moreSvg,

  filter: filterSvg,

  // View toggle
  viewList: viewListSvg,
  viewBlocks: viewBlocksSvg,

  // Theme toggle
  moon: moonSvg,
  sun: sunSvg,

  // Favorites
  star: starSvg,
  starOutline: starOutlineSvg,

  // Objects
  document: documentSvg,
  folder: folderSvg,
  project: projectSvg,
  application: applicationSvg,

  // Help and documentation
  help: helpSvg,

  // Access control
  lock: lockSvg,
  share: shareSvg,
} as const;

export type IconName = keyof typeof icons;
