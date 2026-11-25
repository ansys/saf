/**
 * Projects Dashboard - Dash Component for GLOW Project Management
 *
 * This package provides React components that integrate with Dash
 * for managing GLOW projects with full CRUD operations.
 */

// Main Dash component
import ProjectsDashboard from "./components/ProjectsDashboard";

// Sub-components (for advanced usage)
import ProjectsList from "./components/ProjectsList";
import ProjectsTable from "./components/ProjectsTable";
import ProjectForm from "./components/ProjectForm";
import ImportExport from "./components/ImportExport";
import ProjectsFilter from "./components/ProjectsFilter";
import Pagination from "./components/Pagination";
import ProjectInfo from "./components/ProjectInfo";
import SolutionMetadata from "./components/SolutionMetadata";

// API client
import { projectsApi, createProjectsApi } from "./api/projectsApi";
export type { ProjectsApiClient } from "./api/projectsApi";

// Types
export type {
  Project,
  ActionResult,
  Notification,
  UploadedFile,
  CreateProjectRequest,
  ModifyProjectRequest,
  ProjectsFilters,
} from "./types/project";

export type { DashComponentProps } from "./props";

// Default export is the main Dash component
export {
  ProjectsDashboard,
  // Sub-components: every component with a generated Python class must be exported, because
  // Dash and proptypes.js look it up in the bundle namespace.
  ProjectsList,
  ProjectsTable,
  ProjectForm,
  ImportExport,
  ProjectsFilter,
  Pagination,
  ProjectInfo,
  SolutionMetadata,
  // API
  projectsApi,
  createProjectsApi,
};
