import { formatFileSize } from "@humansignal/core";
import { IconErrorAlt, IconFileUpload, IconInfoOutline, IconUpload } from "@humansignal/icons";
import { cn as scn } from "@humansignal/shad/utils";
import Input from "libs/datamanager/src/components/Common/Input/Input";
import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, SimpleCard, Tooltip, Typography } from "@humansignal/ui";
import truncate from "truncate-middle";
import { API, useAPI } from "../../providers/ApiProvider";
import { cn } from "../../utils/bem";
import { unique } from "../../utils/helpers";
import "../CreateProject/Import/Import.prefix.css";

const importClass = cn("upload_page");
const dropzoneClass = cn("dropzone");

const FLASH_ANIMATION_DURATION = 2000;
const FILENAME_TRUNCATE_START = 24;
const FILENAME_TRUNCATE_END = 24;

function flatten(nested) {
  return [].concat(...nested);
}

const supportedExtensions = {
  text: ["txt"],
  audio: ["wav", "mp3", "flac", "m4a", "ogg"],
  video: ["mp4", "webm"],
  image: ["bmp", "gif", "jpg", "jpeg", "png", "svg", "webp"],
  html: ["html", "htm", "xml"],
  pdf: ["pdf"],
  structuredData: ["csv", "tsv", "json"],
};
const allSupportedExtensions = flatten(Object.values(supportedExtensions));

function getFileExtension(fileName) {
  if (!fileName) return fileName;
  return fileName.split(".").pop().toLowerCase();
}

function traverseFileTree(item, path) {
  return new Promise((resolve) => {
    path = path || "";
    if (item.isFile) {
      if (item.name[0] === ".") return resolve([]);
      resolve([item]);
    } else if (item.isDirectory) {
      const dirReader = item.createReader();
      const dirPath = `${path + item.name}/`;
      dirReader.readEntries((entries) => {
        Promise.all(entries.map((entry) => traverseFileTree(entry, dirPath)))
          .then(flatten)
          .then(resolve);
      });
    }
  });
}

function getFiles(files) {
  return new Promise((resolve) => {
    if (!files.length) return resolve([]);
    if (!files[0].webkitGetAsEntry) return resolve(files);

    const entries = Array.from(files).map((file) => file.webkitGetAsEntry());

    Promise.all(entries.map(traverseFileTree))
      .then(flatten)
      .then((fileEntries) => fileEntries.map((fileEntry) => new Promise((res) => fileEntry.file(res))))
      .then((filePromises) => Promise.all(filePromises))
      .then(resolve);
  });
}

const Upload = ({ children, sendFiles }) => {
  const [hovered, setHovered] = useState(false);
  const onHover = (e) => {
    e.preventDefault();
    setHovered(true);
  };
  const onLeave = setHovered.bind(null, false);
  const dropzoneRef = useRef();

  const onDrop = useCallback(
    (e) => {
      e.preventDefault();
      onLeave();
      getFiles(e.dataTransfer.items).then((files) => sendFiles(files));
    },
    [onLeave, sendFiles],
  );

  return (
    <div
      className={dropzoneClass.mod({ hovered }).toClassName()}
      ref={dropzoneRef}
      onDragStart={onHover}
      onDragOver={onHover}
      onDragLeave={onLeave}
      onDrop={onDrop}
    >
      {children}
    </div>
  );
};

const ErrorMessage = ({ error }) => {
  if (!error) return null;
  let extra = error.validation_errors ?? error.extra;
  if (extra && typeof extra === "object" && !Array.isArray(extra)) {
    extra = extra.non_field_errors ?? Object.values(extra);
  }
  if (Array.isArray(extra)) extra = extra.join("; ");

  return (
    <div className={importClass.elem("error").toClassName()}>
      <IconErrorAlt width="24" height="24" />
      {error.id && `[${error.id}] `}
      {error.detail || error.message}
      {extra && ` (${extra})`}
    </div>
  );
};

export const WorkspaceImportPage = ({ workspace, show = true, onWaiting, onFileListUpdate }) => {
  const { t } = useTranslation();
  const [error, setError] = useState();
  const [newlyUploadedFiles, setNewlyUploadedFiles] = useState(new Set());
  const prevUploadedRef = useRef(new Set());
  const api = useAPI();
  const urlRef = useRef();

  const processFiles = (state, action) => {
    if (action.sending) {
      return { ...state, uploading: [...action.sending, ...state.uploading] };
    }
    if (action.sent) {
      return {
        ...state,
        uploading: state.uploading.filter((f) => !action.sent.includes(f)),
      };
    }
    if (action.uploaded) {
      return {
        ...state,
        uploaded: unique([...state.uploaded, ...action.uploaded], (a, b) => a.id === b.id),
      };
    }
    if (action.ids) {
      const ids = unique([...state.ids, ...action.ids]);
      onFileListUpdate?.(ids);
      return { ...state, ids };
    }
    return state;
  };

  const [files, dispatch] = useReducer(processFiles, {
    uploaded: [],
    uploading: [],
    ids: [],
  });
  const showList = Boolean(files.uploaded?.length || files.uploading?.length);

  const loadFilesList = useCallback(
    async (file_upload_ids) => {
      if (!workspace?.id) return [];
      const query = {};
      if (file_upload_ids) {
        query.ids = JSON.stringify(file_upload_ids);
      }
      const files = await api.callApi("workspaceFileUploads", {
        params: { pk: workspace.id, ...query },
      });
      dispatch({ uploaded: files ?? [] });
      if (files?.length) {
        dispatch({ ids: files.map((f) => f.id) });
      }
      return files;
    },
    [workspace?.id, api],
  );

  const onError = (err) => {
    console.error(err);
    if (typeof err === "string" && err.includes("RequestDataTooBig")) {
      const message = t("createProject.import.fileTooBig");
      const extra = err.match(/"exception_value">(.*)<\/pre>/)?.[1];
      err = { message, extra };
    }
    setError(err);
    onWaiting?.(false);
  };

  const onFinish = useCallback(
    async (res) => {
      const { file_upload_ids } = res;
      dispatch({ ids: file_upload_ids });
      onWaiting?.(false);
      await loadFilesList(file_upload_ids);
      return res;
    },
    [loadFilesList, onWaiting],
  );

  useEffect(() => {
    const currentUploadedIds = new Set(files.uploaded.map((f) => f.id));
    const previousUploadedIds = prevUploadedRef.current;
    const justUploaded = new Set([...currentUploadedIds].filter((id) => !previousUploadedIds.has(id)));
    prevUploadedRef.current = new Set(currentUploadedIds);

    setNewlyUploadedFiles((prev) => {
      const filtered = new Set([...prev].filter((id) => currentUploadedIds.has(id)));
      return filtered;
    });

    if (justUploaded.size > 0) {
      setNewlyUploadedFiles((prev) => new Set([...prev, ...justUploaded]));
      const timeoutId = setTimeout(() => {
        setNewlyUploadedFiles((prev) => {
          const updated = new Set(prev);
          justUploaded.forEach((id) => updated.delete(id));
          return updated;
        });
      }, FLASH_ANIMATION_DURATION);
      return () => clearTimeout(timeoutId);
    }
  }, [files.uploaded]);

  const importFilesImmediately = useCallback(
    async (filesToSend, body) => {
      if (!workspace?.id) {
        onError(new Error("Workspace not ready."));
        return;
      }
      dispatch({ sending: filesToSend });
      const contentType =
        body instanceof FormData ? "multipart/form-data" : "application/x-www-form-urlencoded";
      const res = await API.invoke(
        "workspaceImportFiles",
        { pk: workspace.id },
        { headers: { "Content-Type": contentType }, body },
      );
      if (res && !res.error) {
        await onFinish(res);
      } else {
        onError(res?.response ?? res);
      }
      dispatch({ sent: filesToSend });
    },
    [workspace?.id, onFinish],
  );

  const sendFiles = useCallback(
    (incoming) => {
      setError(null);
      onWaiting?.(true);
      const list = [...incoming];
      const fd = new FormData();
      for (const f of list) {
        if (!allSupportedExtensions.includes(getFileExtension(f.name))) {
          onError(new Error(t("createProject.import.filetypeNotSupported", { name: f.name })));
          return;
        }
        fd.append(f.name, f);
      }
      return importFilesImmediately(list, fd);
    },
    [importFilesImmediately, onWaiting, t],
  );

  const onUpload = useCallback(
    (e) => {
      sendFiles(e.target.files);
      e.target.value = "";
    },
    [sendFiles],
  );

  const onLoadURL = useCallback(
    (e) => {
      e.preventDefault();
      setError(null);
      const url = urlRef.current?.value;
      if (!url) return;
      urlRef.current.value = "";
      onWaiting?.(true);
      const body = new URLSearchParams({ url });
      importFilesImmediately([{ name: url }], body);
    },
    [importFilesImmediately, onWaiting],
  );

  useEffect(() => {
    if (workspace?.id !== undefined) {
      loadFilesList();
    }
  }, [workspace?.id, loadFilesList]);

  if (!workspace) return null;
  if (!show) return null;

  return (
    <div className={importClass}>
      <input
        id="workspace-file-input"
        type="file"
        name="file"
        multiple
        onChange={onUpload}
        style={{ display: "none" }}
      />

      <header className="flex gap-4">
        <form
          className={`${importClass.elem("url-form")} inline-flex items-stretch`}
          method="POST"
          onSubmit={onLoadURL}
        >
          <Input
            placeholder={t("createProject.import.datasetUrl")}
            name="url"
            ref={urlRef}
            rawClassName="h-[40px]"
          />
          <Button variant="primary" look="outlined" type="submit" aria-label={t("createProject.import.addUrl")}>
            {t("createProject.import.addUrl")}
          </Button>
        </form>
        <span>{t("common.or")}</span>
        <Button
          variant="primary"
          look="outlined"
          type="button"
          onClick={() => document.getElementById("workspace-file-input").click()}
          leading={<IconUpload />}
          aria-label={t("createProject.import.uploadFileAriaLabel")}
        >
          {files.uploaded.length ? t("createProject.import.uploadMoreFiles") : t("createProject.import.uploadFiles")}
        </Button>
        <div className={importClass.elem("status").toClassName()}>
          {files.uploaded.length ? t("createProject.import.filesUploaded", { count: files.uploaded.length }) : ""}
        </div>
      </header>

      <ErrorMessage error={error} />

      <main>
        <Upload sendFiles={sendFiles}>
          <div
            className={scn("flex gap-4 w-full min-h-full", {
              "justify-center": !showList,
            })}
          >
            {!showList && (
              <div className="flex gap-4 justify-center items-start w-full h-full">
                <label htmlFor="workspace-file-input" className="w-full h-full">
                  <div className={`${dropzoneClass.elem("content")} w-full`}>
                    <IconFileUpload height="64" className={dropzoneClass.elem("icon").toClassName()} />
                    <header>
                      {t("createProject.import.dropHere")}
                      <br />
                      {t("createProject.import.orClickToBrowse")}
                    </header>

                    <dl>
                      <dt>{t("createProject.import.images")}</dt>
                      <dd>{supportedExtensions.image.join(", ")}</dd>
                      <dt>{t("createProject.import.audio")}</dt>
                      <dd>{supportedExtensions.audio.join(", ")}</dd>
                      <dt>
                        <div className="flex items-center gap-1">
                          {t("createProject.import.video")}
                          <Tooltip title={t("createProject.import.videoTooltip")}>
                            <a
                              href="https://labelstud.io/tags/video#Video-format"
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center"
                              aria-label={t("createProject.import.videoAriaLabel")}
                            >
                              <IconInfoOutline className="w-4 h-4 text-primary-content hover:text-primary-content-hover" />
                            </a>
                          </Tooltip>
                        </div>
                      </dt>
                      <dd>{supportedExtensions.video.join(", ")}</dd>
                      <dt>{t("createProject.import.html")}</dt>
                      <dd>{supportedExtensions.html.join(", ")}</dd>
                      <dt>{t("createProject.import.text")}</dt>
                      <dd>{supportedExtensions.text.join(", ")}</dd>
                      <dt>{t("createProject.import.structuredData")}</dt>
                      <dd>{supportedExtensions.structuredData.join(", ")}</dd>
                      <dt>{t("createProject.import.pdf")}</dt>
                      <dd>{supportedExtensions.pdf.join(", ")}</dd>
                    </dl>
                    <div className="tips">
                      <b>{t("createProject.import.important")}</b>
                      <ul className="mt-2 ml-4 list-disc font-normal">
                        <li>
                          {t("createProject.import.tipCloudStorageLead")}
                          <a href="https://labelstud.io/guide/storage.html" target="_blank" rel="noopener noreferrer">
                            {t("createProject.import.tipCloudStorageLink")}
                          </a>
                          {t("createProject.import.tipCloudStorageMiddle")}
                          <a
                            href="https://labelstud.io/guide/tasks.html#Import-data-from-the-Label-Studio-UI"
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            {t("createProject.import.tipUploadLimitsLink")}
                          </a>
                          {t("createProject.import.tipCloudStorageTrailing")}
                        </li>
                        <li>
                          {t("createProject.import.tipPdfLead")}
                          <a
                            href="https://labelstud.io/templates/multi-page-document-annotation"
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            {t("createProject.import.tipPdfLink")}
                          </a>
                          {t("createProject.import.tipPdfTrailing")}
                        </li>
                        <li>
                          {t("createProject.import.tipPreannotatedLead")}
                          <a target="_blank" href="https://labelstud.io/guide/predictions.html" rel="noreferrer">
                            {t("createProject.import.tipPreannotatedLink")}
                          </a>
                          {t("createProject.import.tipPreannotatedTrailing")}
                        </li>
                      </ul>
                    </div>
                  </div>
                </label>
              </div>
            )}

            {showList && (
              <div className="w-full">
                <SimpleCard
                  title={t("createProject.import.filesCard")}
                  className="w-full h-full"
                  contentClassName="overflow-y-auto h-[calc(100%-48px)]"
                >
                  <table className="w-full">
                    <tbody>
                      {files.uploaded.map((file) => {
                        const truncatedFilename = truncate(
                          file.file,
                          FILENAME_TRUNCATE_START,
                          FILENAME_TRUNCATE_END,
                          "...",
                        );
                        return (
                          <tr
                            key={file.file}
                            className={newlyUploadedFiles.has(file.id) ? importClass.elem("upload-flash") : ""}
                          >
                            <td className={importClass.elem("file-name").toClassName()}>
                              <Tooltip title={file.file}>
                                <Typography variant="body" size="small" className="truncate">
                                  {truncatedFilename}
                                </Typography>
                              </Tooltip>
                            </td>
                            <td>
                              <span className={importClass.elem("file-status").toClassName()} />
                            </td>
                            <td className={importClass.elem("file-size").toClassName()}>
                              <Typography
                                variant="body"
                                size="smaller"
                                className="text-nowrap text-neutral-content-subtle text-right"
                              >
                                {file.size ? formatFileSize(file.size) : ""}
                              </Typography>
                            </td>
                          </tr>
                        );
                      })}
                      {files.uploading.map((file, idx) => {
                        const truncatedFilename = truncate(
                          file.name,
                          FILENAME_TRUNCATE_START,
                          FILENAME_TRUNCATE_END,
                          "...",
                        );
                        return (
                          <tr key={`${idx}-${file.name}`}>
                            <td className={importClass.elem("file-name").toClassName()}>
                              <Tooltip title={file.name}>
                                <Typography variant="body" size="small" className="truncate">
                                  {truncatedFilename}
                                </Typography>
                              </Tooltip>
                            </td>
                            <td>
                              <span
                                className={importClass.elem("file-status").mod({ uploading: true }).toClassName()}
                              />
                            </td>
                            <td className={importClass.elem("file-size").toClassName()}>&nbsp;</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </SimpleCard>
              </div>
            )}
          </div>
        </Upload>
      </main>
    </div>
  );
};
