import React, { useCallback, useEffect, useMemo, useState } from "react";
import { ProjectAccess } from "../types/project";
import { createAccessApi } from "../api/accessApi";
import { usersApi } from "../api/usersApi";
import { userLabel } from "./AccessCells";

type ShareDialogProps = {
  /** Id of the project, with or without the `projects/` prefix. */
  projectId: string;
  /** Display name of the project, shown in the title. */
  projectName?: string;
  /** Base URL of the GLOW API. */
  apiBaseUrl?: string;
  /** Base URL of the Dash server that serves the user directory routes. */
  usersApiBaseUrl?: string;
  /**
   * `share` manages the members of the project (owner). `assignOwner` makes a user the
   * owner of a project that has none (super admin).
   */
  mode?: "share" | "assignOwner";
  /** Called when the dialog should be closed. */
  onClose: () => void;
  /** Called after the access state of the project changed. */
  onChanged?: (access: ProjectAccess) => void;
};

const errorMessage = (err: unknown): string =>
  err instanceof Error ? err.message : "Unknown error";

/**
 * Dialog to share a project with other users, remove them, or hand the project over.
 * Users are typed as an e-mail address or username and resolved through the user directory.
 */
const ShareDialog: React.FC<ShareDialogProps> = ({
  projectId,
  projectName,
  apiBaseUrl,
  usersApiBaseUrl,
  mode = "share",
  onClose,
  onChanged,
}) => {
  const api = useMemo(() => createAccessApi(apiBaseUrl), [apiBaseUrl]);
  const [access, setAccess] = useState<ProjectAccess | null>(null);
  const [names, setNames] = useState<Record<string, string>>({});
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadNames = useCallback(
    async (ids: string[]) => {
      if (ids.length === 0) return;
      try {
        const resolved = await usersApi.names(ids, usersApiBaseUrl);
        setNames((prev) => ({ ...prev, ...resolved }));
      } catch {
        // Without a directory the ids are shown in short form.
      }
    },
    [usersApiBaseUrl],
  );

  const applyAccess = useCallback(
    (next: ProjectAccess) => {
      setAccess(next);
      void loadNames(next.members.map((m) => m.user_id));
    },
    [loadNames],
  );

  useEffect(() => {
    if (mode !== "share") return;
    let cancelled = false;
    api
      .getAccess(projectId)
      .then((loaded) => {
        if (!cancelled) applyAccess(loaded);
      })
      .catch((err) => {
        if (!cancelled) setError(errorMessage(err));
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, projectId, mode]);

  const run = async (operation: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await operation();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const typed = text.trim();
    if (!typed || busy) return;
    void run(async () => {
      const userId = await usersApi.resolve(typed, usersApiBaseUrl);
      if (userId === null) {
        setError(`No user found for "${typed}"`);
        return;
      }
      if (mode === "assignOwner") {
        const next = await api.assignOwner(projectId, userId);
        onChanged?.(next);
        onClose();
        return;
      }
      const next = await api.share(projectId, userId);
      applyAccess(next);
      setText("");
      onChanged?.(next);
    });
  };

  const handleRemove = (userId: string) =>
    run(async () => {
      const next = await api.unshare(projectId, userId);
      applyAccess(next);
      onChanged?.(next);
    });

  const handleMakeOwner = (userId: string) =>
    run(async () => {
      const next = await api.transferOwnership(projectId, userId);
      onChanged?.(next);
      onClose();
    });

  const title = mode === "assignOwner" ? "Assign owner" : "Share project";

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-content share-dialog"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
      >
        <h3>
          {title}
          {projectName ? `: ${projectName}` : ""}
        </h3>

        <form className="share-dialog-form" onSubmit={handleSubmit}>
          <label htmlFor="share-dialog-user">E-mail or username</label>
          <div className="share-dialog-input-row">
            <input
              id="share-dialog-user"
              type="text"
              value={text}
              onChange={(e) => setText(e.target.value)}
              disabled={busy}
              autoComplete="off"
            />
            <button
              type="submit"
              className="awc-btn awc-btn-primary"
              disabled={busy || text.trim() === ""}
            >
              {mode === "assignOwner" ? "Assign owner" : "Add"}
            </button>
          </div>
        </form>

        {error && (
          <div className="error-message" role="alert">
            {error}
          </div>
        )}

        {mode === "share" && access && (
          <ul className="share-dialog-members">
            {access.members.map((member) => {
              const isOwner = member.role === "owner";
              return (
                <li key={member.user_id} className="share-dialog-member">
                  <span className="share-dialog-member-name">
                    {userLabel(member.user_id, names)}
                  </span>
                  <span className="share-dialog-member-role">
                    {isOwner ? "Owner" : "Viewer"}
                  </span>
                  {!isOwner && (
                    <span className="share-dialog-member-actions">
                      <button
                        type="button"
                        className="awc-btn awc-btn-secondary"
                        disabled={busy}
                        onClick={() => handleMakeOwner(member.user_id)}
                      >
                        Make owner
                      </button>
                      <button
                        type="button"
                        className="awc-btn awc-btn-secondary"
                        disabled={busy}
                        onClick={() => handleRemove(member.user_id)}
                      >
                        Remove
                      </button>
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        )}

        <div className="modal-actions">
          <button
            type="button"
            className="awc-btn awc-btn-secondary"
            onClick={onClose}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default ShareDialog;
