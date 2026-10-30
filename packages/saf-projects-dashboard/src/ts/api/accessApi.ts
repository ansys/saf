/**
 * Project access control API client for the GLOW backend.
 *
 * Covers ownership, sharing, the write lock and write requests:
 * - `GET  /access/me`
 * - `GET  /projects/{id}/access`
 * - `POST /projects/{id}/access/members`, `DELETE /projects/{id}/access/members/{user_id}`
 * - `POST /projects/{id}/access:transfer-ownership`, `POST /projects/{id}/access:assign-owner`
 * - `POST /projects/{id}/lock:acquire|release|take-over|force-release`
 * - `POST /projects/{id}/write-requests` and `.../write-requests/{request_id}:approve|deny|withdraw`
 *
 * Same conventions as `projectsApi`: every method takes an optional `baseUrl`.
 * Project ids may be given with or without the `projects/` prefix.
 */
import { AccessMe, ProjectAccess, WriteRequest } from "../types/project";
import { buildUrl, handleResponse } from "./projectsApi";

const JSON_HEADERS = { "Content-Type": "application/json" };

function projectPath(projectId: string): string {
  return `/projects/${projectId.replace(/^projects\//, "")}`;
}

async function post<T>(path: string, baseUrl?: string, body?: unknown) {
  const response = await fetch(buildUrl(path, baseUrl), {
    method: "POST",
    headers: JSON_HEADERS,
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  return handleResponse<T>(response);
}

export interface AccessApiClient {
  getMe: (baseUrl?: string) => Promise<AccessMe>;
  getAccess: (projectId: string, baseUrl?: string) => Promise<ProjectAccess>;
  share: (
    projectId: string,
    userId: string,
    baseUrl?: string,
  ) => Promise<ProjectAccess>;
  unshare: (
    projectId: string,
    userId: string,
    baseUrl?: string,
  ) => Promise<ProjectAccess>;
  transferOwnership: (
    projectId: string,
    userId: string,
    baseUrl?: string,
  ) => Promise<ProjectAccess>;
  assignOwner: (
    projectId: string,
    userId: string,
    baseUrl?: string,
  ) => Promise<ProjectAccess>;
  acquire: (projectId: string, baseUrl?: string) => Promise<ProjectAccess>;
  release: (projectId: string, baseUrl?: string) => Promise<ProjectAccess>;
  takeOver: (projectId: string, baseUrl?: string) => Promise<ProjectAccess>;
  forceRelease: (projectId: string, baseUrl?: string) => Promise<ProjectAccess>;
  requestWrite: (projectId: string, baseUrl?: string) => Promise<WriteRequest>;
  approve: (
    projectId: string,
    requestId: string,
    baseUrl?: string,
  ) => Promise<ProjectAccess>;
  deny: (
    projectId: string,
    requestId: string,
    baseUrl?: string,
  ) => Promise<ProjectAccess>;
  withdraw: (
    projectId: string,
    requestId: string,
    baseUrl?: string,
  ) => Promise<ProjectAccess>;
}

const requestAction =
  (action: "approve" | "deny" | "withdraw") =>
  (projectId: string, requestId: string, baseUrl?: string) =>
    post<ProjectAccess>(
      `${projectPath(projectId)}/write-requests/${encodeURIComponent(requestId)}:${action}`,
      baseUrl,
    );

const lockAction =
  (action: "acquire" | "release" | "take-over" | "force-release") =>
  (projectId: string, baseUrl?: string) =>
    post<ProjectAccess>(`${projectPath(projectId)}/lock:${action}`, baseUrl);

const userAction =
  (
    suffix:
      "/access/members" | "/access:transfer-ownership" | "/access:assign-owner",
  ) =>
  (projectId: string, userId: string, baseUrl?: string) =>
    post<ProjectAccess>(`${projectPath(projectId)}${suffix}`, baseUrl, {
      user_id: userId,
    });

export const accessApi: AccessApiClient = {
  /** GET /access/me - Who the caller is, as far as access control is concerned. */
  getMe: async (baseUrl?: string): Promise<AccessMe> => {
    const response = await fetch(buildUrl("/access/me", baseUrl), {
      method: "GET",
      headers: JSON_HEADERS,
    });
    return handleResponse<AccessMe>(response);
  },

  /** GET /projects/{id}/access - Access state of the project. */
  getAccess: async (
    projectId: string,
    baseUrl?: string,
  ): Promise<ProjectAccess> => {
    const response = await fetch(
      buildUrl(`${projectPath(projectId)}/access`, baseUrl),
      { method: "GET", headers: JSON_HEADERS },
    );
    return handleResponse<ProjectAccess>(response);
  },

  /** POST /projects/{id}/access/members - Share the project, as a viewer. Owner only. */
  share: userAction("/access/members"),

  /** DELETE /projects/{id}/access/members/{user_id} - Stop sharing. Owner only. */
  unshare: async (
    projectId: string,
    userId: string,
    baseUrl?: string,
  ): Promise<ProjectAccess> => {
    const response = await fetch(
      buildUrl(
        `${projectPath(projectId)}/access/members/${encodeURIComponent(userId)}`,
        baseUrl,
      ),
      { method: "DELETE", headers: JSON_HEADERS },
    );
    return handleResponse<ProjectAccess>(response);
  },

  /** POST /projects/{id}/access:transfer-ownership - Give the project to a member. Owner only. */
  transferOwnership: userAction("/access:transfer-ownership"),

  /** POST /projects/{id}/access:assign-owner - Make a user the owner. Super admins only. */
  assignOwner: userAction("/access:assign-owner"),

  /** POST /projects/{id}/lock:acquire - Take the write lock when it is free. */
  acquire: lockAction("acquire"),

  /** POST /projects/{id}/lock:release - Release the write lock. Holder only. */
  release: lockAction("release"),

  /** POST /projects/{id}/lock:take-over - Take the lock from its holder. Owner only. */
  takeOver: lockAction("take-over"),

  /** POST /projects/{id}/lock:force-release - Release the lock whoever holds it. Super admins only. */
  forceRelease: lockAction("force-release"),

  /** POST /projects/{id}/write-requests - Ask the holder for the write lock. */
  requestWrite: (projectId: string, baseUrl?: string) =>
    post<WriteRequest>(`${projectPath(projectId)}/write-requests`, baseUrl),

  /** POST /projects/{id}/write-requests/{request_id}:approve - Owner or holder. */
  approve: requestAction("approve"),

  /** POST /projects/{id}/write-requests/{request_id}:deny - Owner or holder. */
  deny: requestAction("deny"),

  /** POST /projects/{id}/write-requests/{request_id}:withdraw - Requester only. */
  withdraw: requestAction("withdraw"),
};

/** Create an access API client with a fixed base URL. */
export function createAccessApi(baseUrl?: string): AccessApiClient {
  return {
    getMe: () => accessApi.getMe(baseUrl),
    getAccess: (id) => accessApi.getAccess(id, baseUrl),
    share: (id, userId) => accessApi.share(id, userId, baseUrl),
    unshare: (id, userId) => accessApi.unshare(id, userId, baseUrl),
    transferOwnership: (id, userId) =>
      accessApi.transferOwnership(id, userId, baseUrl),
    assignOwner: (id, userId) => accessApi.assignOwner(id, userId, baseUrl),
    acquire: (id) => accessApi.acquire(id, baseUrl),
    release: (id) => accessApi.release(id, baseUrl),
    takeOver: (id) => accessApi.takeOver(id, baseUrl),
    forceRelease: (id) => accessApi.forceRelease(id, baseUrl),
    requestWrite: (id) => accessApi.requestWrite(id, baseUrl),
    approve: (id, requestId) => accessApi.approve(id, requestId, baseUrl),
    deny: (id, requestId) => accessApi.deny(id, requestId, baseUrl),
    withdraw: (id, requestId) => accessApi.withdraw(id, requestId, baseUrl),
  };
}

export default accessApi;
