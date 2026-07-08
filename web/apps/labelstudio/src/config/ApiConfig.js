export const API_CONFIG = {
  gateway: `${window.APP_SETTINGS.hostname}/api`,
  endpoints: {
    // Users
    users: "/users",
    updateUser: "PATCH:/users/:pk",
    updateUserAvatar: "POST:/users/:pk/avatar",
    deleteUserAvatar: "DELETE:/users/:pk/avatar",
    me: "/current-user/whoami",
    hotkeys: "GET:/current-user/hotkeys/",
    updateHotkeys: "PATCH:/current-user/hotkeys/",

    // Organization
    memberships: "/organizations/:pk/memberships",
    userMemberships: "/organizations/:pk/memberships/:userPk",
    inviteLink: "/invite",
    resetInviteLink: "POST:/invite/reset-token",
    createInvitation: "POST:/invitations",

    // Project
    projects: "/projects",
    project: "/projects/:pk",
    updateProject: "PATCH:/projects/:pk",
    createProject: "POST:/projects",
    deleteProject: "DELETE:/projects/:pk",
    projectResetCache: "POST:/projects/:pk/summary/reset",

    // Review workflow
    reviewTasks: "/projects/:pk/review/tasks",
    reviewCandidates: "/projects/:pk/review/candidates",
    reviewProgress: "/projects/:pk/review/progress",
    submitReview: "POST:/annotations/:pk/review",

    // Project members (role management)
    projectMembers: "/projects/:pk/members",
    createProjectMember: "POST:/projects/:pk/members",
    updateProjectMember: "PATCH:/projects/:pk/members/:memberPk",
    deleteProjectMember: "DELETE:/projects/:pk/members/:memberPk",

    // Workspaces
    workspaces: "/workspaces",
    workspace: "/workspaces/:pk",
    createWorkspace: "POST:/workspaces",
    updateWorkspace: "PATCH:/workspaces/:pk",
    deleteWorkspace: "DELETE:/workspaces/:pk",
    workspaceMembers: "/workspaces/:pk/members",
    workspaceMember: "/workspaces/:pk/members/:memberPk",
    createWorkspaceMember: "POST:/workspaces/:pk/members",
    updateWorkspaceMember: "PATCH:/workspaces/:pk/members/:memberPk",
    deleteWorkspaceMember: "DELETE:/workspaces/:pk/members/:memberPk",
    workspaceSummary: "/workspaces/:pk/summary",
    workspaceProjects: "/workspaces/:pk/projects",
    createWorkspaceProject: "POST:/workspaces/:pk/projects",
    workspaceDatasets: "/workspaces/:pk/datasets",
    workspaceFileUploads: "/workspaces/:pk/file-uploads",
    uploadWorkspaceFiles: "POST:/workspaces/:pk/file-uploads",
    deleteWorkspaceFileUpload: "DELETE:/workspaces/:pk/file-uploads/:uploadPk",
    workspaceImportFiles: "POST:/workspaces/:pk/import",
    workspaceImportPredictions: "POST:/workspaces/:pk/import/predictions",
    workspaceWorkload: "/workspaces/:pk/workload",

    // Datasets / Task Pools
    workspaceTaskSourceItems: "/workspaces/:pk/task-source-items",
    taskPools: "/workspaces/:pk/task-pools",
    createTaskPool: "POST:/workspaces/:pk/task-pools",
    taskPool: "/workspaces/:pk/task-pools/:poolPk",
    updateTaskPool: "PATCH:/workspaces/:pk/task-pools/:poolPk",
    deleteTaskPool: "DELETE:/workspaces/:pk/task-pools/:poolPk",
    addTaskPoolItems: "POST:/workspaces/:pk/task-pools/:poolPk/items",
    removeTaskPoolItems: "DELETE:/workspaces/:pk/task-pools/:poolPk/items",

    // Compensation
    projectCompensationPolicy: "/projects/:pk/compensation-policy",
    setProjectCompensationPolicy: "PUT:/projects/:pk/compensation-policy",
    workspaceCompensation: "/workspaces/:pk/compensation",
    memberCompensation: "/workspaces/:pk/compensation/members/:userPk",
    workspacePayments: "/workspaces/:pk/payments",
    createWorkspacePayment: "POST:/workspaces/:pk/payments",
    deleteWorkspacePayment: "DELETE:/workspaces/:pk/payments/:paymentPk",

    // Workspace-scope cloud storage templates (provider in path: s3 | gcs | azure | localfiles)
    // NOTE: extra params (e.g. `workspace`) are auto-appended as the query string.
    workspaceStorages: "/storages/:provider/workspace",
    createWorkspaceStorage: "POST:/storages/:provider/workspace/",
    workspaceStorage: "/storages/:provider/workspace/:pk",
    updateWorkspaceStorage: "PATCH:/storages/:provider/workspace/:pk",
    deleteWorkspaceStorage: "DELETE:/storages/:provider/workspace/:pk",
    assignWorkspaceStorageToProject: "POST:/storages/:provider/workspace/:pk/assign",
    syncWorkspaceStorage: "POST:/storages/:provider/workspace/:pk/sync",

    // Presigning
    presignUrlForTask: "/../tasks/:taskID/presign",
    presignUrlForProject: "/../projects/:projectId/presign",

    // Config and Import
    configTemplates: "/templates",
    validateConfig: "POST:/projects/:pk/validate",
    createSampleTask: "POST:/projects/:pk/sample-task",
    fileUploads: "/projects/:pk/file-uploads",
    deleteFileUploads: "DELETE:/projects/:pk/file-uploads",
    importFiles: "POST:/projects/:pk/import",
    reimportFiles: "POST:/projects/:pk/reimport",
    dataSummary: "/projects/:pk/summary",

    // DM
    deleteTabs: "DELETE:/dm/views/reset",

    // Storages
    listStorages: "/storages/:target?",
    storageTypes: "/storages/:target?/types",
    storageForms: "/storages/:target?/:type/form",
    createStorage: "POST:/storages/:target?/:type",
    deleteStorage: "DELETE:/storages/:target?/:type/:pk",
    updateStorage: "PATCH:/storages/:target?/:type/:pk",
    syncStorage: "POST:/storages/:target?/:type/:pk/sync",
    validateStorage: "POST:/storages/:target?/:type/validate",
    storageFiles: "POST:/storages/:target?/:type/files",

    // ML
    mlBackends: "GET:/ml",
    mlBackend: "GET:/ml/:pk",
    addMLBackend: "POST:/ml",
    updateMLBackend: "PATCH:/ml/:pk",
    deleteMLBackend: "DELETE:/ml/:pk",
    trainMLBackend: "POST:/ml/:pk/train",
    predictWithML: "POST:/ml/:pk/predict/test",
    projectModelVersions: "/projects/:pk/model-versions",
    deletePredictions: "DELETE:/projects/:pk/model-versions",
    modelVersions: "/ml/:pk/versions",
    mlInteractive: "POST:/ml/:pk/interactive-annotating",

    // Export
    export: "/projects/:pk/export",
    previousExports: "/projects/:pk/export/files",
    exportFormats: "/projects/:pk/export/formats",

    // Version
    version: "/version",

    // Webhook
    webhooks: "/webhooks",
    webhook: "/webhooks/:pk",
    updateWebhook: "PATCH:/webhooks/:pk",
    createWebhook: "POST:/webhooks",
    deleteWebhook: "DELETE:/webhooks/:pk",
    webhooksInfo: "/webhooks/info",

    // Product tours
    getProductTour: "GET:/current-user/product-tour",
    updateProductTour: "PATCH:/current-user/product-tour",

    // Tokens
    accessTokenList: "GET:/token",
    accessTokenGetRefreshToken: "POST:/token",
    accessTokenRevoke: "POST:/token/blacklist",

    accessTokenSettings: "GET:/jwt/settings",
    accessTokenUpdateSettings: "POST:/jwt/settings",

    // FSM
    fsmStateHistory: "GET:/fsm/entities/:entityType/:entityId/history",
  },
  alwaysExpectJSON: false,
};
