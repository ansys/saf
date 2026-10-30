import React from "react";
import { ProjectsViewProps } from "./ProjectsList";
import { icons } from "../utils/icons";
import { ProjectIcon, formatDate } from "./ProjectUtils";
import ContextMenu from "./ContextMenu";
import {
  EditingCell,
  LockIcon,
  OwnerCell,
  PendingBadge,
  buildProjectMenuItems,
} from "./AccessCells";
import "../styles/ProjectsTable.css";

/**
 * ProjectsTable component displays projects in a table/list layout.
 * Each row shows the same data and actions as the card view:
 * Icon | Name | Created | Last Saved | Favorite | Info | Context Menu
 *
 * With project access control on, the Name is followed by Owner and
 * Editing now (with a lock icon while someone holds the write lock).
 */
const ProjectsTable: React.FC<ProjectsViewProps> = ({
  projects,
  projectIconUrl,
  onEdit,
  onDelete,
  onExport,
  onCardClick,
  onFavoriteToggle,
  onInfo,
  favoriteIds,
  accessMe,
  userNames,
  myPendingRequests,
  onAccessAction,
}) => {
  if (projects.length === 0) {
    return (
      <div className="no-projects">
        <p>No projects found. Create your first project to get started!</p>
      </div>
    );
  }

  const showAccess = projects.some((project) => !!project.access);

  return (
    <div className="projects-table-container">
      <table className="projects-table">
        <thead>
          <tr>
            <th className="col-icon">
              <span className="sr-only">Icon</span>
            </th>
            <th className="col-name">Name</th>
            {showAccess && <th className="col-owner">Owner</th>}
            {showAccess && <th className="col-editing">Editing now</th>}
            <th className="col-id">Id</th>
            <th className="col-date">Created</th>
            <th className="col-date">Last Saved</th>
            <th className="col-action">
              <span className="sr-only">Info</span>
            </th>
            <th className="col-action">
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {projects.map((project) => {
            const menuItems = buildProjectMenuItems({
              project,
              me: accessMe,
              myRequestId: myPendingRequests?.[project.name],
              onEdit,
              onExport,
              onDelete,
              onAccessAction,
            });
            return (
              <tr
                key={project.name}
                className="projects-table-row"
                onClick={() => onCardClick(project.name)}
                tabIndex={0}
                aria-label={`Open project ${project.display_name}`}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    onCardClick(project.name);
                  }
                }}
              >
                <td className="col-icon">
                  <ProjectIcon src={project.icon ?? projectIconUrl} />
                </td>
                <td className="col-name">
                  {project.display_name}
                  <PendingBadge project={project} me={accessMe} />
                </td>
                {showAccess && (
                  <td className="col-owner">
                    {project.access && (
                      <OwnerCell project={project} names={userNames} />
                    )}
                  </td>
                )}
                {showAccess && (
                  <td className="col-editing">
                    {project.access && (
                      <>
                        <EditingCell project={project} names={userNames} />
                        <LockIcon project={project} />
                      </>
                    )}
                  </td>
                )}
                <td className="col-id">
                  <span className="projectid-label">
                    {project.name.replace(/^projects\//, "")}
                  </span>
                </td>
                <td className="col-date">{formatDate(project.date_created)}</td>
                <td className="col-date">
                  {formatDate(project.date_modified)}
                </td>
                <td className="col-action">
                  <button
                    className="btn-icon"
                    onClick={(e) => {
                      e.stopPropagation();
                      onInfo(project.name);
                    }}
                    title="Project info"
                    aria-label="Project info"
                  >
                    <span
                      className="awc-icon"
                      dangerouslySetInnerHTML={{ __html: icons.infoOutline }}
                    />
                  </button>
                </td>
                <td className="col-action">
                  {menuItems.length > 0 && <ContextMenu items={menuItems} />}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

export default ProjectsTable;
