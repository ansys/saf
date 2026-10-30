/**
 * TypeScript type definitions for Projects Dashboard
 * Based on GLOW API OpenAPI schema (ProjectInfo, CreateProjectRequest, ModifyProjectRequest)
 */

/**
 * Project information returned by the GLOW API.
 * Matches the ProjectInfo schema from OpenAPI specification.
 */
export interface Project {
  /** The URI path identifying the project resource (e.g., "projects/2ztdlpa2") */
  name: string;
  /** The project name displayed to the user */
  display_name: string;
  /** Optional project description */
  description?: string;
  /** Date and time of creation (ISO 8601 format) */
  date_created?: string;
  /** Date and time of last modification (ISO 8601 format) */
  date_modified?: string;
  /** URL for the project icon (per-project custom icon from the API) */
  icon?: string;
  /**
   * Who owns, holds the write lock of and has access to the project.
   * `null` or absent when project access control is disabled.
   */
  access?: ProjectAccessSummary | null;
}

/** Role of a user in a project. */
export type ProjectRole = "owner" | "viewer";

/** Access summary carried by each project of the list when access control is on. */
export interface ProjectAccessSummary {
  owner_id: string | null;
  holder_id: string | null;
  my_role: ProjectRole | null;
  pending_request_count: number;
}

/** Who the calling user is, as far as project access control is concerned. */
export interface AccessMe {
  user_id: string | null;
  is_super_admin: boolean;
}

export interface ProjectMember {
  user_id: string;
  role: ProjectRole;
}

export interface WriteRequest {
  id: string;
  requester_id: string;
  status: "pending" | "approved" | "denied" | "withdrawn";
  created_at: string;
  decided_by?: string | null;
  decided_at?: string | null;
}

/** Full access state of a project, as seen by the calling user. */
export interface ProjectAccess {
  project_id: string;
  owner_id: string | null;
  members: ProjectMember[];
  holder_id: string | null;
  lock_acquired_at: string | null;
  last_write_at: string | null;
  version: number;
  pending_requests: WriteRequest[];
  my_role: ProjectRole | null;
  can_write: boolean;
  is_orphan: boolean;
}

/**
 * Request body for creating a new project.
 * Matches CreateProjectRequest schema.
 */
export interface CreateProjectRequest {
  /** The project name displayed to the user */
  display_name: string;
  /** The project description optionally displayed to the user */
  description?: string;
}

/**
 * Request body for modifying an existing project.
 * Matches ModifyProjectRequest schema.
 */
export interface ModifyProjectRequest {
  /** The project name displayed to the user */
  display_name: string;
  /** The project description optionally displayed to the user */
  description?: string;
}

/**
 * Notification message displayed to the user.
 */
export interface Notification {
  /** The notification message text */
  message: string;
  /** Notification type for styling */
  type: "success" | "error" | "info" | "warning";
}

/**
 * Result of a CRUD action, emitted via setProps for Python callbacks.
 */
export interface ActionResult {
  /** The type of action performed */
  action:
    | "create"
    | "update"
    | "delete"
    | "import"
    | "export"
    | "upgrade"
    | "list";
  /** The project ID involved in the action (if applicable) */
  projectId?: string;
  /** Whether the action was successful */
  success: boolean;
  /** Human-readable message describing the result */
  message?: string;
  /** Timestamp of the action (milliseconds since epoch) */
  timestamp: number;
}

/**
 * File upload data from Dash dcc.Upload component.
 * The dcc.Upload provides base64-encoded file content.
 */
export interface UploadedFile {
  /** Base64-encoded file content (data URL format: "data:application/octet-stream;base64,...") */
  contents: string;
  /** Original filename */
  filename: string;
  /** Last modified timestamp */
  lastModified?: number;
}

/**
 * API error response structure.
 */
export interface APIError {
  /** Error detail message */
  detail?: string | { msg: string; type: string }[];
}

/**
 * Date-range filters for `GET /projects` (GLOW projects API).
 * All dates are ISO `YYYY-MM-DD` strings; omitted fields mean no bound.
 */
export interface ProjectsFilters {
  /** Inclusive search input text for display name search. */
  search?: string;
  /** Inclusive lower bound on `date_created`. */
  dateCreatedFrom?: string;
  /** Inclusive upper bound on `date_created`. */
  dateCreatedTo?: string;
  /** Inclusive lower bound on `date_modified`. */
  dateModifiedFrom?: string;
  /** Inclusive upper bound on `date_modified`. */
  dateModifiedTo?: string;
  /** Only list the projects without owner (super admins only). */
  orphansOnly?: boolean;
}

/**
 * Paginated response shape for `GET /projects?page=&page_size=`.
 * Matches the GLOW server response documented in the Solution projects API.
 */
export interface PaginatedProjects {
  /** Projects on the requested page. */
  projects: Project[];
  /** 1-based index of the current page. */
  current_page: number;
  /** Total number of pages available for the current page_size. */
  total_pages: number;
  /** Page size used by the server when computing the response. */
  page_size: number;
  /** Total number of projects matching the query across all pages. */
  total_projects: number;
}
