import React from "react";
import { AccessMe, Project } from "../types/project";
import { icons } from "../utils/icons";
import { MenuItem } from "./ContextMenu";

/** Access-control actions a project menu can trigger. */
export type AccessAction =
  | "share"
  | "assignOwner"
  | "acquire"
  | "release"
  | "takeOver"
  | "forceRelease"
  | "requestWrite"
  | "withdraw"
  | "approve"
  | "deny";

/** Display name of a user; users the directory does not know are shown by a short id. */
export const userLabel = (
  userId: string,
  names: Record<string, string> = {},
): string => names[userId] ?? `unknown user (${userId.slice(0, 8)}…)`;

/** Whether the user can decide on the write requests of the project (owner or lock holder). */
export const canDecideRequests = (
  project: Project,
  me: AccessMe | null | undefined,
): boolean => {
  const access = project.access;
  if (!access) return false;
  const isHolder = !!me?.user_id && access.holder_id === me.user_id;
  return access.my_role === "owner" || isHolder;
};

export const OwnerCell: React.FC<{
  project: Project;
  names?: Record<string, string>;
}> = ({ project, names }) => {
  const ownerId = project.access?.owner_id;
  return (
    <span className="access-owner">
      {ownerId ? userLabel(ownerId, names) : "No owner"}
    </span>
  );
};

export const EditingCell: React.FC<{
  project: Project;
  names?: Record<string, string>;
}> = ({ project, names }) => {
  const holderId = project.access?.holder_id;
  return (
    <span className="access-editing">
      {holderId ? userLabel(holderId, names) : "—"}
    </span>
  );
};

export const LockIcon: React.FC<{ project: Project }> = ({ project }) =>
  project.access?.holder_id ? (
    <span
      className="awc-icon access-lock-icon"
      role="img"
      aria-label="Locked"
      title="Someone is editing this project"
      dangerouslySetInnerHTML={{ __html: icons.lock }}
    />
  ) : null;

/** Count of pending write requests, shown only to the people who can decide on them. */
export const PendingBadge: React.FC<{
  project: Project;
  me?: AccessMe | null;
}> = ({ project, me }) => {
  const count = project.access?.pending_request_count ?? 0;
  if (count <= 0 || !canDecideRequests(project, me)) return null;
  const label = `${count} pending write request${count === 1 ? "" : "s"}`;
  return (
    <span className="pending-badge" aria-label={label} title={label}>
      {count}
    </span>
  );
};

type MenuContext = {
  project: Project;
  me?: AccessMe | null;
  /** Id of my pending write request on the project, when I know of one. */
  myRequestId?: string;
  onEdit: (project: Project) => void;
  onExport: (projectId: string) => void;
  onDelete: (projectId: string) => void;
  onAccessAction?: (action: AccessAction, project: Project) => void;
};

/**
 * Items of the context menu of a project.
 *
 * With access control off (`project.access` is null or absent) these are today's items. With it on they depend on
 * the role of the user: owner, lock holder, viewer, or super admin who is not a member.
 */
export function buildProjectMenuItems(ctx: MenuContext): MenuItem[] {
  const { project, me, myRequestId, onEdit, onExport, onDelete } = ctx;
  const access = project.access;

  const edit: MenuItem = {
    label: "Edit",
    icon: icons.edit,
    onClick: () => onEdit(project),
  };
  const exportItem: MenuItem = {
    label: "Export",
    icon: icons.download,
    onClick: () => onExport(project.name),
  };
  const del: MenuItem = {
    label: "Delete",
    icon: icons.delete,
    onClick: () => onDelete(project.name),
    className: "menu-item-danger",
  };

  if (!access) return [edit, exportItem, del];

  const act = (
    action: AccessAction,
    label: string,
    icon: string,
  ): MenuItem => ({
    label,
    icon,
    onClick: () => ctx.onAccessAction?.(action, project),
  });
  const approveDeny = (): MenuItem[] =>
    access.pending_request_count > 0
      ? [
          act("approve", "Approve", icons.check),
          act("deny", "Deny", icons.close),
        ]
      : [];

  const myId = me?.user_id ?? null;
  const isHolder = !!myId && access.holder_id === myId;
  const heldByOther = !!access.holder_id && !isHolder;

  if (access.my_role === "owner") {
    return [
      act("share", "Share…", icons.share),
      ...(heldByOther ? [act("takeOver", "Take over lock", icons.lock)] : []),
      ...(isHolder ? [act("release", "Release lock", icons.lock)] : []),
      ...approveDeny(),
      exportItem,
      del,
    ];
  }

  if (access.my_role === "viewer") {
    if (isHolder) {
      return [act("release", "Release lock", icons.lock), ...approveDeny()];
    }
    if (!access.holder_id) {
      return [act("acquire", "Start editing", icons.edit)];
    }
    return myRequestId
      ? [act("withdraw", "Withdraw request", icons.close)]
      : [act("requestWrite", "Request write access", icons.lock)];
  }

  if (me?.is_super_admin) {
    return [
      act("assignOwner", "Assign owner…", icons.share),
      act("forceRelease", "Force release", icons.lock),
      del,
    ];
  }

  return [];
}
