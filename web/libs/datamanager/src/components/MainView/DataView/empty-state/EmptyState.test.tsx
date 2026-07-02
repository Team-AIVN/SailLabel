import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { EmptyState } from "./EmptyState";

// Mock the external dependencies
jest.mock("@humansignal/ui", () => ({
  Button: ({ children, onClick, disabled, "data-testid": testId, ...props }: any) => (
    <button onClick={onClick} disabled={disabled} data-testid={testId} {...props}>
      {children}
    </button>
  ),
  Typography: ({ children, className, ...props }: any) => (
    <div className={className} {...props}>
      {children}
    </div>
  ),
}));

jest.mock("@humansignal/icons", () => ({
  IconLsLabeling: ({ width, height }: any) => <span data-testid="icon-ls-labeling" width={width} height={height} />,
  IconCheck: ({ width, height }: any) => <span data-testid="icon-check" width={width} height={height} />,
  IconSearch: ({ width, height }: any) => <span data-testid="icon-search" width={width} height={height} />,
  IconInbox: ({ width, height }: any) => <span data-testid="icon-inbox" width={width} height={height} />,
}));

describe("EmptyState Component", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("Default (no project-level import) state", () => {
    it("shows 'No Task pool assigned' when the project has no Task pool", () => {
      render(<EmptyState project={{}} />);

      expect(screen.getByText("No Task pool assigned")).toBeInTheDocument();
      expect(
        screen.getByText(
          "No Task pool is assigned to this project. Datasets are imported and managed in the workspace, then assigned to a project as a Task pool.",
        ),
      ).toBeInTheDocument();
    });

    it("shows a neutral no-data message when a Task pool is assigned but empty", () => {
      render(<EmptyState project={{ work_pool: 7 }} />);

      expect(screen.getByText("No data to display")).toBeInTheDocument();
      expect(screen.getByText("This project's Task pool has no items yet.")).toBeInTheDocument();
    });

    it("never renders any data-import affordances", () => {
      render(<EmptyState project={{}} />);

      // No import button, no connect-cloud-storage button, no storage icons, no docs link.
      expect(screen.queryByTestId("dm-import-button")).not.toBeInTheDocument();
      expect(screen.queryByTestId("dm-connect-source-storage-button")).not.toBeInTheDocument();
      expect(screen.queryByTestId("dm-storage-provider-icons")).not.toBeInTheDocument();
      expect(screen.queryByTestId("dm-docs-data-import-link")).not.toBeInTheDocument();
      expect(screen.queryByText("Import data to get your project started")).not.toBeInTheDocument();
    });
  });

  describe("Filter-based Empty State", () => {
    it("should render filter empty state when hasFilters is true", () => {
      render(<EmptyState hasFilters={true} onClearFilters={jest.fn()} />);

      expect(screen.getByText("No tasks found")).toBeInTheDocument();
      expect(screen.getByText("Try adjusting or clearing the filters to see more results")).toBeInTheDocument();
      expect(screen.getByTestId("dm-clear-filters-button")).toBeInTheDocument();
      expect(screen.getByTestId("icon-search")).toBeInTheDocument();
    });

    it("should call onClearFilters when Clear Filters button is clicked", async () => {
      const user = userEvent.setup();
      const mockClearFilters = jest.fn();

      render(<EmptyState hasFilters={true} onClearFilters={mockClearFilters} />);

      await user.click(screen.getByTestId("dm-clear-filters-button"));

      expect(mockClearFilters).toHaveBeenCalledTimes(1);
    });
  });

  describe("Reviewer Role", () => {
    it("should render reviewer empty state", () => {
      render(<EmptyState userRole="REVIEWER" />);

      expect(screen.getByText("No tasks available for review or labeling")).toBeInTheDocument();
      expect(screen.getByText("Tasks imported to this project will appear here")).toBeInTheDocument();
      expect(screen.getByTestId("icon-check")).toBeInTheDocument();
    });
  });

  describe("Annotator Role", () => {
    it("should render annotator auto-distribution state with Label All Tasks button", () => {
      const project = { assignment_settings: { label_stream_task_distribution: "auto_distribution" } };

      render(<EmptyState userRole="ANNOTATOR" project={project} onLabelAllTasks={jest.fn()} />);

      expect(screen.getByText("Start labeling tasks")).toBeInTheDocument();
      expect(screen.getByText("Tasks you've labeled will appear here")).toBeInTheDocument();
      expect(screen.getByTestId("dm-label-all-tasks-button")).toBeInTheDocument();
      expect(screen.getByTestId("icon-ls-labeling")).toBeInTheDocument();
    });

    it("should call onLabelAllTasks when Label All Tasks button is clicked", async () => {
      const user = userEvent.setup();
      const mockLabelAllTasks = jest.fn();
      const project = { assignment_settings: { label_stream_task_distribution: "auto_distribution" } };

      render(<EmptyState userRole="ANNOTATOR" project={project} onLabelAllTasks={mockLabelAllTasks} />);

      await user.click(screen.getByTestId("dm-label-all-tasks-button"));

      expect(mockLabelAllTasks).toHaveBeenCalledTimes(1);
    });

    it("should render annotator manual distribution state without button", () => {
      const project = { assignment_settings: { label_stream_task_distribution: "assigned_only" } };

      render(<EmptyState userRole="ANNOTATOR" project={project} />);

      expect(screen.getByText("No tasks available")).toBeInTheDocument();
      expect(screen.getByText("Tasks assigned to you will appear here")).toBeInTheDocument();
      expect(screen.getByTestId("icon-inbox")).toBeInTheDocument();
      expect(screen.queryByTestId("dm-label-all-tasks-button")).not.toBeInTheDocument();
    });

    it("should render fallback annotator state for unknown distribution setting", () => {
      const project = { assignment_settings: { label_stream_task_distribution: "unknown_setting" } };

      render(<EmptyState userRole="ANNOTATOR" project={project} />);

      expect(screen.getByText("No tasks available")).toBeInTheDocument();
      expect(screen.getByText("Tasks will appear here when they become available")).toBeInTheDocument();
      expect(screen.getByTestId("icon-inbox")).toBeInTheDocument();
    });
  });

  describe("Edge Cases", () => {
    it("should handle missing project object gracefully for annotators", () => {
      render(<EmptyState userRole="ANNOTATOR" />);

      expect(screen.getByText("No tasks available")).toBeInTheDocument();
      expect(screen.getByText("Tasks will appear here when they become available")).toBeInTheDocument();
    });

    it("should render the no-work-pool state when no project is provided", () => {
      render(<EmptyState />);

      expect(screen.getByText("No Task pool assigned")).toBeInTheDocument();
    });
  });
});
