/**
 * Projects API Client for GLOW Backend
 *
 * Provides a configurable API client that can use either:
 * - Relative URLs for same-origin requests via Flask proxy (default)
 * - Absolute URLs when apiBaseUrl is provided from Python
 *
 * All endpoints are based on the GLOW API OpenAPI specification.
 */

import {
  Project,
  CreateProjectRequest,
  ModifyProjectRequest,
  APIError,
  PaginatedProjects,
  ProjectsFilters,
} from "../types/project";

/**
 * Custom error class for API errors that preserves the HTTP status code.
 */
export class ApiError extends Error {
  public readonly status: number;
  public readonly statusText: string;

  constructor(status: number, statusText: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.statusText = statusText;
  }
}

/**
 * Helper function to handle API responses.
 * Throws an ApiError with status code and details if the response is not OK.
 */
export async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const errorData: APIError = await response.json();
      if (typeof errorData.detail === "string") {
        errorMessage = errorData.detail;
      } else if (Array.isArray(errorData.detail)) {
        errorMessage = errorData.detail.map((e) => e.msg).join(", ");
      }
    } catch {
      // Response body is not JSON, use default message
    }
    throw new ApiError(response.status, response.statusText, errorMessage);
  }

  // Handle empty responses (204 No Content)
  const contentType = response.headers.get("content-type");
  if (!contentType || !contentType.includes("application/json")) {
    return {} as T;
  }

  return response.json();
}

/**
 * Build the full URL for an API endpoint.
 * If baseUrl is provided, prepends it to the path. Otherwise, uses relative URLs.
 *
 * @param path - The API path (e.g., "/projects", "/projects/123")
 * @param baseUrl - Optional base URL (e.g., "http://127.0.0.1:5678")
 * @returns The full URL to use for the API call
 */
export function buildUrl(path: string, baseUrl?: string): string {
  if (baseUrl) {
    // Remove trailing slash from baseUrl if present
    const normalizedBase = baseUrl.endsWith("/")
      ? baseUrl.slice(0, -1)
      : baseUrl;
    return `${normalizedBase}${path}`;
  }
  return path;
}

/** Map camelCase filter fields to GLOW `GET /projects` query params. */

function appendFilterParams(filters?: ProjectsFilters): string | undefined {
  if (!filters) return;

  const conditions: string[] = [];

  if (filters.search?.trim()) {
    const escapedSearch = filters.search.trim().replace(/"/g, '\\"');
    conditions.push(`display_name = "${escapedSearch}"`);
  }

  if (filters.dateCreatedFrom) {
    conditions.push(`date_created >= ${filters.dateCreatedFrom}`);
  }

  if (filters.dateCreatedTo) {
    conditions.push(`date_created <= ${filters.dateCreatedTo}`);
  }

  if (filters.dateModifiedFrom) {
    conditions.push(`date_modified >= ${filters.dateModifiedFrom}`);
  }

  if (filters.dateModifiedTo) {
    conditions.push(`date_modified <= ${filters.dateModifiedTo}`);
  }

  return conditions.length ? conditions.join(" AND ") : undefined;
}

/**
 * Interface for the Projects API client.
 * All methods accept an optional baseUrl parameter for flexibility.
 */
export interface ProjectsApiClient {
  listProjects: (
    page?: number,
    pageSize?: number,
    filters?: ProjectsFilters,
    baseUrl?: string,
  ) => Promise<PaginatedProjects>;
  createProject: (
    displayName: string,
    description?: string,
    baseUrl?: string,
  ) => Promise<Project>;
  getProject: (projectId: string, baseUrl?: string) => Promise<Project>;
  updateProject: (
    projectId: string,
    displayName: string,
    description?: string,
    baseUrl?: string,
  ) => Promise<Project>;
  deleteProject: (projectId: string, baseUrl?: string) => Promise<void>;
  exportProject: (projectId: string, baseUrl?: string) => Promise<Blob>;
  importProject: (
    fileContent: string,
    filename: string,
    displayName: string,
    baseUrl?: string,
  ) => Promise<Project>;
  upgradeProject: (projectId: string, baseUrl?: string) => Promise<Project>;
}

/**
 * Projects API endpoints for GLOW backend.
 * All methods accept an optional baseUrl parameter:
 * - If baseUrl is provided, uses absolute URLs (e.g., "http://127.0.0.1:5678/projects")
 * - If baseUrl is omitted, uses relative URLs (e.g., "/projects") for Flask proxy mode
 */
export const projectsApi: ProjectsApiClient = {
  /**
   * GET /projects - List projects (paginated, optionally filtered)
   * Returns the page of projects matching `page`, `page_size`, and any date-range
   * filters, along with pagination metadata (current_page, total_pages, page_size,
   * total_projects). When called without arguments, GLOW applies its defaults.
   */
  listProjects: async (
    page?: number,
    pageSize?: number,
    filters?: ProjectsFilters,
    baseUrl?: string,
  ): Promise<PaginatedProjects> => {
    const params = new URLSearchParams();
    if (page !== undefined) params.set("page", String(page));
    if (pageSize !== undefined) params.set("page_size", String(pageSize));
    const filterExpression = appendFilterParams(filters);
    if (filterExpression) params.set("filter", filterExpression);
    if (filters?.orphansOnly) params.set("orphans_only", "true");
    const query = params.toString();
    const path = query ? `/projects?${query}` : "/projects";
    const response = await fetch(buildUrl(path, baseUrl), {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    });
    return handleResponse<PaginatedProjects>(response);
  },

  /**
   * POST /projects - Create a new project
   * Create a project with the given display_name.
   */
  createProject: async (
    displayName: string,
    description?: string,
    baseUrl?: string,
  ): Promise<Project> => {
    const body: CreateProjectRequest = {
      display_name: displayName,
      description: description || "", // Optional description can be added later via updateProject
    };

    const response = await fetch(buildUrl("/projects", baseUrl), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
    return handleResponse<Project>(response);
  },

  /**
   * GET /projects/{project_id} - Get project details
   * Return details for a specific project.
   */
  getProject: async (projectId: string, baseUrl?: string): Promise<Project> => {
    const response = await fetch(buildUrl(`/${projectId}`, baseUrl), {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    });
    return handleResponse<Project>(response);
  },

  /**
   * PATCH /projects/{project_id} - Modify project
   * Modify details for a specific project.
   */
  updateProject: async (
    projectId: string,
    displayName: string,
    description?: string,
    baseUrl?: string,
  ): Promise<Project> => {
    const body: ModifyProjectRequest = {
      display_name: displayName,
      description: description,
    };

    const response = await fetch(buildUrl(`/${projectId}`, baseUrl), {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
    return handleResponse<Project>(response);
  },

  /**
   * DELETE /projects/{project_id} - Delete project
   * Delete the project from the database and delete its project directory.
   */
  deleteProject: async (projectId: string, baseUrl?: string): Promise<void> => {
    const response = await fetch(buildUrl(`/${projectId}`, baseUrl), {
      method: "DELETE",
      headers: {
        "Content-Type": "application/json",
      },
    });
    await handleResponse<void>(response);
  },

  /**
   * GET /projects/{project_id}:export - Export project
   * Export the given project as a .safx file.
   */
  exportProject: async (projectId: string, baseUrl?: string): Promise<Blob> => {
    const response = await fetch(buildUrl(`/${projectId}:export`, baseUrl), {
      method: "GET",
    });

    if (!response.ok) {
      throw new Error(`Failed to export project: ${response.statusText}`);
    }

    return response.blob();
  },

  /**
   * POST /projects:import - Import project
   * Import the given project with the specified display_name.
   * Accepts base64-encoded file content from dcc.Upload.
   *
   * @param fileContent - Base64 data URL from dcc.Upload (e.g., "data:application/octet-stream;base64,...")
   * @param filename - Original filename
   * @param displayName - Project display name
   * @param baseUrl - Optional base URL for the API
   */
  importProject: async (
    fileContent: string,
    filename: string,
    displayName: string,
    baseUrl?: string,
  ): Promise<Project> => {
    // Extract base64 data from data URL format
    const base64Data = fileContent.split(",")[1] || fileContent;

    // Convert base64 to Blob
    const binaryString = atob(base64Data);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    const blob = new Blob([bytes], { type: "application/octet-stream" });

    // Create FormData for multipart upload
    const formData = new FormData();
    formData.append("safx_file", blob, filename);
    formData.append("display_name", displayName);

    const response = await fetch(buildUrl("/projects:import", baseUrl), {
      method: "POST",
      body: formData,
      // Note: Don't set Content-Type header - browser will set it with boundary
    });
    return handleResponse<Project>(response);
  },

  /**
   * POST /projects/{project_id}:upgrade - Upgrade project
   * Upgrade the details of a solution data stored in a specific project.
   */
  upgradeProject: async (
    projectId: string,
    baseUrl?: string,
  ): Promise<Project> => {
    const response = await fetch(buildUrl(`/${projectId}:upgrade`, baseUrl), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    });
    return handleResponse<Project>(response);
  },
};

/**
 * Factory function to create a pre-configured API client with a fixed baseUrl.
 * This is useful when you want to create an API client instance with a specific
 * base URL and use it throughout the component.
 *
 * @param baseUrl - The base URL for the GLOW API (e.g., "http://127.0.0.1:5678")
 * @returns A configured API client with all methods bound to the specified baseUrl
 *
 * @example
 * const api = createProjectsApi("http://127.0.0.1:5678");
 * const page = await api.listProjects(1, 15); // Uses the configured baseUrl
 */
export function createProjectsApi(baseUrl?: string): ProjectsApiClient {
  return {
    listProjects: (
      page?: number,
      pageSize?: number,
      filters?: ProjectsFilters,
    ) => projectsApi.listProjects(page, pageSize, filters, baseUrl),
    createProject: (displayName: string, description?: string) =>
      projectsApi.createProject(displayName, description, baseUrl),
    getProject: (projectId: string) =>
      projectsApi.getProject(projectId, baseUrl),
    updateProject: (
      projectId: string,
      displayName: string,
      description?: string,
    ) =>
      projectsApi.updateProject(projectId, displayName, description, baseUrl),
    deleteProject: (projectId: string) =>
      projectsApi.deleteProject(projectId, baseUrl),
    exportProject: (projectId: string) =>
      projectsApi.exportProject(projectId, baseUrl),
    importProject: (
      fileContent: string,
      filename: string,
      displayName: string,
    ) => projectsApi.importProject(fileContent, filename, displayName, baseUrl),
    upgradeProject: (projectId: string) =>
      projectsApi.upgradeProject(projectId, baseUrl),
  };
}

export default projectsApi;
