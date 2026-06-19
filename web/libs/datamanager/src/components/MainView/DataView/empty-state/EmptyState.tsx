import React, { type FC, type ReactNode } from "react";
import { IconLsLabeling, IconCheck, IconSearch, IconInbox } from "@humansignal/icons";
import { Button, Typography } from "@humansignal/ui";

// TypeScript interfaces for props
interface EmptyStateProps {
  // Role-based props (optional)
  userRole?: string;
  project?: {
    // Project-scoped dataset import is removed; data comes from an assigned Work Pool.
    work_pool?: number | string | null;
    assignment_settings?: {
      label_stream_task_distribution?: "auto_distribution" | "assigned_only" | string;
    };
  };
  hasData?: boolean;
  hasFilters?: boolean;
  canLabel?: boolean;
  onLabelAllTasks?: () => void;
  onClearFilters?: () => void;
}

// Internal helper interfaces and types
interface EmptyStateLayoutProps {
  icon: ReactNode;
  iconBackground?: string;
  iconColor?: string;
  title: string;
  description: string;
  actions?: ReactNode;
  additionalContent?: ReactNode;
  footer?: ReactNode;
  testId?: string;
  ariaLabelledBy?: string;
  ariaDescribedBy?: string;
  wrapperClassName?: string;
}

// Internal helper function to render common empty state structure
const renderEmptyStateLayout = ({
  icon,
  iconBackground = "bg-primary-emphasis",
  iconColor = "text-primary-icon",
  title,
  description,
  actions,
  additionalContent,
  footer,
  testId,
  ariaLabelledBy,
  ariaDescribedBy,
  wrapperClassName = "w-full h-full flex flex-col items-center justify-center text-center p-wide",
}: EmptyStateLayoutProps) => {
  // Clone the icon and ensure it has consistent 40x40 size
  const iconWithSize = React.cloneElement(icon as React.ReactElement, {
    width: 40,
    height: 40,
  });

  const content = (
    <div className={wrapperClassName}>
      <div className={`flex items-center justify-center ${iconBackground} ${iconColor} rounded-full p-tight mb-4`}>
        {iconWithSize}
      </div>

      <Typography variant="headline" size="medium" className="mb-tight" id={ariaLabelledBy}>
        {title}
      </Typography>

      <Typography
        size="medium"
        className={`text-neutral-content-subtler max-w-xl ${actions || additionalContent ? "mb-tight" : ""}`}
        id={ariaDescribedBy}
      >
        {description}
      </Typography>

      {additionalContent}

      {actions &&
        (() => {
          // Flatten children and filter out null/false values to count actual rendered elements
          const flattenedActions = React.Children.toArray(actions).flat().filter(Boolean);
          const actualActionCount = flattenedActions.length;
          const isSingleAction = actualActionCount === 1;

          return (
            <div className={`flex ${isSingleAction ? "justify-center" : ""} gap-base w-full max-w-md mt-base`}>
              {actions}
            </div>
          );
        })()}

      {footer && <div className="mt-6">{footer}</div>}
    </div>
  );

  // For import state, we need special wrapper structure
  if (testId === "empty-state-label") {
    return (
      <div
        data-testid={testId}
        aria-labelledby={ariaLabelledBy}
        aria-describedby={ariaDescribedBy}
        className="w-full flex items-center justify-center m-0"
      >
        <div className="w-full h-full">{content}</div>
      </div>
    );
  }

  // For all other states
  return content;
};

/**
 * Unified empty state for Data Manager
 * Handles different empty states based on user role and context
 *
 * Project-scoped dataset import is intentionally NOT offered here: datasets are
 * imported and managed at the workspace level, then assigned to a project as a
 * Work Pool. The default state reports the project's work pool status instead.
 *
 * Props:
 * - userRole: string — User role (REVIEWER, ANNOTATOR, etc.) - optional
 * - project: object — Project object with work_pool + assignment settings - optional
 * - hasData: boolean — Whether the project has any tasks - optional
 * - hasFilters: boolean — Whether filters are currently applied - optional
 * - canLabel: boolean — Whether the Label All Tasks button would be enabled - optional
 * - onLabelAllTasks: function — Callback for Label All Tasks action - optional
 * - onClearFilters: function — Callback to clear all applied filters - optional
 */

export const EmptyState: FC<EmptyStateProps> = ({
  // Role-based props (optional)
  userRole,
  project,
  hasData: _hasData,
  hasFilters,
  canLabel: _canLabel,
  onLabelAllTasks,
  onClearFilters,
}) => {
  // If filters are applied, show the filter-specific empty state (regardless of user role)
  if (hasFilters) {
    return renderEmptyStateLayout({
      icon: <IconSearch />,
      iconBackground: "bg-warning-background",
      iconColor: "text-warning-icon",
      title: "No tasks found",
      description: "Try adjusting or clearing the filters to see more results",
      actions: (
        <Button variant="primary" look="outlined" onClick={onClearFilters} data-testid="dm-clear-filters-button">
          Clear Filters
        </Button>
      ),
    });
  }

  // Role-based empty state logic (from RoleBasedEmptyState)
  // For service roles (reviewers/annotators), show role-specific empty states when they have no visible tasks
  // This applies whether the project has tasks or not - what matters is what's visible to this user
  if (userRole === "REVIEWER" || userRole === "ANNOTATOR") {
    // Reviewer empty state
    if (userRole === "REVIEWER") {
      return renderEmptyStateLayout({
        icon: <IconCheck />,
        title: "No tasks available for review or labeling",
        description: "Tasks imported to this project will appear here",
      });
    }

    // Annotator empty state
    if (userRole === "ANNOTATOR") {
      const isAutoDistribution = project?.assignment_settings?.label_stream_task_distribution === "auto_distribution";
      const isManualDistribution = project?.assignment_settings?.label_stream_task_distribution === "assigned_only";

      if (isAutoDistribution) {
        return renderEmptyStateLayout({
          icon: <IconLsLabeling />,
          title: "Start labeling tasks",
          description: "Tasks you've labeled will appear here",
          actions: (
            <Button
              variant="primary"
              look="filled"
              disabled={false}
              onClick={onLabelAllTasks}
              data-testid="dm-label-all-tasks-button"
            >
              Label All Tasks
            </Button>
          ),
        });
      }

      if (isManualDistribution) {
        return renderEmptyStateLayout({
          icon: <IconInbox />,
          title: "No tasks available",
          description: "Tasks assigned to you will appear here",
        });
      }

      // Fallback for annotators with unknown distribution setting
      return renderEmptyStateLayout({
        icon: <IconInbox width={40} height={40} />,
        title: "No tasks available",
        description: "Tasks will appear here when they become available",
      });
    }
  }

  // Default case: project-scoped data import is disabled. Datasets are imported at the
  // workspace level and assigned to a project as a Work Pool, so we only report the
  // work pool status here — no import / cloud-storage affordances.
  const hasWorkPool = Boolean(project?.work_pool);
  return renderEmptyStateLayout({
    icon: <IconInbox />,
    title: hasWorkPool ? "No data to display" : "No work pool assigned",
    description: hasWorkPool
      ? "This project's work pool has no items yet."
      : "No work pool is assigned to this project. Datasets are imported and managed in the workspace, then assigned to a project as a work pool.",
  });
};
