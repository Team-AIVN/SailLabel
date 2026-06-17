import React from "react";

export const useWorkspaceImport = () => {
  const [uploading, setUploadingStatus] = React.useState(false);
  const [fileIds, setFileIds] = React.useState([]);

  const pageProps = {
    onWaiting: setUploadingStatus,
    onFileListUpdate: setFileIds,
  };

  return { uploading, fileIds, pageProps };
};
