"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import PageHeader from "@/components/dashboard/PageHeader";
import StatusBadge from "@/components/ui/StatusBadge";
import NoticeBanner from "@/components/ui/NoticeBanner";
import EmptyState from "@/components/ui/EmptyState";
import MaterialIcon from "@/components/ui/MaterialIcon";
import { TableSkeleton } from "@/components/ui/Skeleton";
import {
  uploadVideo,
  getVideoJob,
  getVideoResults,
  listVideoJobs,
} from "@/lib/api/video-analytics";
import type { VideoJob, VideoResultsResponse, VideoDetectionBox } from "@/types/detection";

const ALLOWED_EXTENSIONS = [".mp4", ".webm", ".mov", ".avi", ".png", ".jpg", ".jpeg"];
const MAX_FILE_SIZE_MB = 200;

export default function VideoAnalyticsPage() {
  const [jobs, setJobs] = useState<VideoJob[]>([]);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [activeResults, setActiveResults] = useState<VideoResultsResponse | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isLoadingJobs, setIsLoadingJobs] = useState(true);
  const [showOverlay, setShowOverlay] = useState(true);
  const [isDragOver, setIsDragOver] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [activePollingJobId, setActivePollingJobId] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  // Clean up preview object URL on unmount or file change
  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  // Clean up polling interval on unmount
  useEffect(() => {
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, []);

  // Fetch job history on mount
  useEffect(() => {
    const controller = new AbortController();

    queueMicrotask(() => {
      setIsLoadingJobs(true);

      listVideoJobs(controller.signal)
        .then((data) => {
          if (Array.isArray(data)) {
            setJobs(data);
            if (data.length > 0 && !activeJobId) {
              setActiveJobId(data[0].id);
            }
          }
        })
        .catch(() => {
          setJobs([]);
        })
        .finally(() => {
          setIsLoadingJobs(false);
        });
    });

    return () => {
      controller.abort();
    };
  }, [activeJobId]);

  // Load results when activeJobId changes
  const loadJobResults = useCallback(async (jobId: string) => {
    try {
      const results = await getVideoResults(jobId);
      setActiveResults(results);
    } catch {
      setActiveResults(null);
    }
  }, []);

  useEffect(() => {
    if (activeJobId) {
      queueMicrotask(() => {
        loadJobResults(activeJobId);
      });
    } else {
      queueMicrotask(() => {
        setActiveResults(null);
      });
    }
  }, [activeJobId, loadJobResults]);

  // Polling for active async processing jobs
  const startPollingJob = useCallback((jobId: string) => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
    }

    setActivePollingJobId(jobId);

    pollingIntervalRef.current = setInterval(async () => {
      try {
        const jobStatus = await getVideoJob(jobId);

        setJobs((prev) => {
          const index = prev.findIndex((j) => j.id === jobId);
          if (index >= 0) {
            const updated = [...prev];
            updated[index] = { ...updated[index], ...jobStatus };
            return updated;
          }
          return [jobStatus, ...prev];
        });

        if (jobStatus.status === "done") {
          if (pollingIntervalRef.current) {
            clearInterval(pollingIntervalRef.current);
            pollingIntervalRef.current = null;
          }
          setActivePollingJobId(null);
          setToastMessage(`CV inference completed for ${jobStatus.file}. Genuine detection metrics ready.`);
          setActiveJobId(jobId);
          loadJobResults(jobId);
        } else if (jobStatus.status === "failed") {
          if (pollingIntervalRef.current) {
            clearInterval(pollingIntervalRef.current);
            pollingIntervalRef.current = null;
          }
          setActivePollingJobId(null);
          setErrorMessage(`Video processing job ${jobId} failed on the backend.`);
        }
      } catch (err) {
        // Network error while polling
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
          pollingIntervalRef.current = null;
        }
        setActivePollingJobId(null);
        setErrorMessage(`Error checking job status: ${(err as Error).message}`);
      }
    }, 2500);
  }, [loadJobResults]);

  const validateAndSetFile = (file: File) => {
    setValidationError(null);
    setErrorMessage(null);

    const extension = "." + file.name.split(".").pop()?.toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(extension)) {
      setValidationError(
        `Unsupported format "${extension}". Please upload an MP4, WebM, MOV, AVI, or Image file.`
      );
      return;
    }

    if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      setValidationError(
        `File size (${(file.size / (1024 * 1024)).toFixed(1)} MB) exceeds maximum allowed limit of ${MAX_FILE_SIZE_MB} MB.`
      );
      return;
    }

    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }

    setSelectedFile(file);
    setPreviewUrl(URL.createObjectURL(file));
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) validateAndSetFile(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) validateAndSetFile(file);
  };

  const handleUploadAndProcess = async () => {
    if (!selectedFile) {
      setValidationError("Please select a video or image file to upload.");
      return;
    }

    setIsUploading(true);
    setErrorMessage(null);
    setValidationError(null);

    try {
      const uploadRes = await uploadVideo(selectedFile);

      const newJob: VideoJob = {
        id: uploadRes.jobId,
        file: uploadRes.filename || selectedFile.name,
        uploaded: "Just now",
        status: uploadRes.status || "queued",
        frames: 0,
        customersDetected: 0,
      };

      setJobs((prev) => [newJob, ...prev]);
      setActiveJobId(uploadRes.jobId);
      setToastMessage(uploadRes.message || `Uploaded ${selectedFile.name}. Processing queued.`);

      // Start asynchronous polling for completion
      startPollingJob(uploadRes.jobId);
    } catch (err) {
      setErrorMessage(
        `Failed to submit video to FastAPI backend: ${(err as Error).message}. Verify that the backend is running at http://localhost:8000.`
      );
    } finally {
      setIsUploading(false);
    }
  };

  const activeJob = jobs.find((j) => j.id === activeJobId);
  const isCurrentlyProcessing = activePollingJobId !== null || activeJob?.status === "processing";

  return (
    <div className="space-y-5">
      {/* Header */}
      <PageHeader
        title="Computer Vision Studio"
        description="Video ingestion, asynchronous YOLO object detection tracking, customer flow reticles, and inference metrics."
      />

      {errorMessage && (
        <NoticeBanner
          type="critical"
          message={errorMessage}
          onDismiss={() => setErrorMessage(null)}
        />
      )}

      {toastMessage && (
        <NoticeBanner
          type="success"
          message={toastMessage}
          onDismiss={() => setToastMessage(null)}
        />
      )}

      {/* Main Studio Two-Column Layout */}
      <div className="grid gap-4 lg:grid-cols-12">
        {/* Left Column: Large CV Video Viewport */}
        <section
          aria-label="Computer vision video stream viewport"
          className="lg:col-span-8 rounded-xl border border-[#e6e7e3] bg-white p-4.5 flex flex-col justify-between"
        >
          <div>
            {/* Viewport Top Bar */}
            <div className="flex flex-wrap items-center justify-between gap-2 pb-3 mb-3 border-b border-[#eeefec]">
              <div className="flex items-center gap-2">
                <div className="flex h-6 w-6 items-center justify-center rounded-md bg-emerald-950 text-emerald-300">
                  <MaterialIcon name="videocam" className="h-3.5 w-3.5" aria-hidden="true" />
                </div>
                <div>
                  <h2 className="font-heading text-sm font-bold text-slate-900 flex items-center gap-2">
                    <span>{activeJob ? activeJob.file : selectedFile ? selectedFile.name : "Video Viewport"}</span>
                    {activeJob && (
                      <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-[#f2f3ef] text-slate-600">
                        Job: {activeJob.id}
                      </span>
                    )}
                  </h2>
                </div>
              </div>

              {/* Viewport Controls */}
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => setShowOverlay(!showOverlay)}
                  className="flex items-center gap-1 rounded-md border border-[#e6e7e3] bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-[#f8f8f6] transition-colors"
                >
                  {showOverlay ? (
                    <>
                      <MaterialIcon name="visibility_off" className="h-3 w-3 text-slate-400" aria-hidden="true" />
                      <span>Hide Reticles</span>
                    </>
                  ) : (
                    <>
                      <MaterialIcon name="visibility" className="h-3 w-3 text-emerald-700" aria-hidden="true" />
                      <span>Show Reticles</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Video Canvas Container */}
            <div className="relative aspect-video w-full overflow-hidden rounded-lg bg-slate-950 border border-slate-800 shadow-inner flex items-center justify-center select-none">
              {previewUrl ? (
                <video
                  ref={videoRef}
                  src={previewUrl}
                  controls
                  className="h-full w-full object-contain"
                  aria-label="Uploaded video preview player"
                />
              ) : (
                <div className="flex flex-col items-center justify-center text-slate-500 p-6 text-center">
                  <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-900 text-slate-600 mb-3 border border-slate-800">
                    <MaterialIcon name="video_file" className="h-8 w-8 text-slate-600" aria-hidden="true" />
                  </div>
                  <p className="font-heading text-sm font-bold text-slate-300">
                    No Video Stream Active
                  </p>
                  <p className="text-xs text-slate-500 mt-1 max-w-sm">
                    Upload an MP4, WebM, MOV, or AVI video to trigger asynchronous computer-vision inference on the FastAPI backend.
                  </p>
                </div>
              )}

              {/* Genuine Bounding Box Visualizations from Backend */}
              {showOverlay && activeResults && activeResults.detections && activeResults.detections.length > 0 && (
                <div className="pointer-events-none absolute inset-0">
                  {/* Subtle Grid Reticle */}
                  <div className="absolute inset-0 bg-[radial-gradient(#10b981_1px,transparent_1px)] [background-size:24px_24px] opacity-10" />

                  {/* Render Genuine Detections */}
                  {activeResults.detections.map((det: VideoDetectionBox, index: number) => {
                    // Normalize bounding box coordinates
                    // Contract: box: { x, y, width, height }
                    // If coordinates are in pixels (e.g. 120, 80) or fractions, clamp gracefully
                    const isNormalized = det.box.width <= 1 && det.box.height <= 1;
                    const left = isNormalized ? `${det.box.x * 100}%` : `${det.box.x}px`;
                    const top = isNormalized ? `${det.box.y * 100}%` : `${det.box.y}px`;
                    const width = isNormalized ? `${det.box.width * 100}%` : `${det.box.width}px`;
                    const height = isNormalized ? `${det.box.height * 100}%` : `${det.box.height}px`;

                    return (
                      <div
                        key={det.id || `det-${index}`}
                        className="absolute border border-emerald-400/90 bg-emerald-500/10 rounded-xs"
                        style={{ left, top, width, height }}
                      >
                        <div className="absolute -top-5 left-0 flex items-center gap-1 rounded bg-emerald-950/90 px-1.5 py-0.5 text-[9px] font-bold text-emerald-300 border border-emerald-600/60 tabular-nums">
                          <span>#{det.id || index + 1}</span>
                          <span className="text-white capitalize">
                            {det.label} {Math.round(det.confidence * 100)}%
                          </span>
                        </div>
                      </div>
                    );
                  })}

                  {/* HUD Telemetry Header */}
                  <div className="absolute top-3 right-3 flex items-center gap-2 rounded bg-black/85 px-2.5 py-1 font-mono text-[10px] text-emerald-400 border border-emerald-800/60 tabular-nums">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                    <span>
                      {activeResults.detections.length} DETECTIONS · {activeResults.totalFrames} FRAMES
                    </span>
                  </div>
                </div>
              )}

              {/* Status overlay when processing */}
              {isCurrentlyProcessing && (
                <div className="absolute inset-0 bg-slate-950/75 backdrop-blur-xs flex flex-col items-center justify-center p-6 text-center text-white">
                  <MaterialIcon name="refresh" className="h-8 w-8 text-emerald-400 animate-spin mb-3" aria-hidden="true" />
                  <p className="font-heading text-sm font-bold">FastAPI Inference in Progress</p>
                  <p className="text-xs text-slate-400 mt-1 max-w-xs">
                    Polling backend job status for {activeJob?.file || "uploaded video"}...
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Viewport Footer Telemetry Metrics */}
          <div className="mt-3 pt-3 border-t border-[#eeefec] grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <div>
              <span className="text-[10px] text-slate-400 block">Total Frames</span>
              <span className="font-semibold text-slate-900 tabular-nums">
                {activeResults?.totalFrames != null
                  ? activeResults.totalFrames.toLocaleString()
                  : activeJob?.frames != null && activeJob.frames > 0
                  ? activeJob.frames.toLocaleString()
                  : "—"}
              </span>
            </div>
            <div>
              <span className="text-[10px] text-slate-400 block">Customers Detected</span>
              <span className="font-semibold text-slate-900 tabular-nums">
                {activeResults?.customersDetected != null
                  ? activeResults.customersDetected.toLocaleString()
                  : activeJob?.customersDetected != null && activeJob.customersDetected > 0
                  ? activeJob.customersDetected.toLocaleString()
                  : "—"}
              </span>
            </div>
            <div>
              <span className="text-[10px] text-slate-400 block">Peak Customer Count</span>
              <span className="font-semibold text-emerald-800 tabular-nums">
                {activeResults?.peakCount != null ? `${activeResults.peakCount} shoppers` : "—"}
              </span>
            </div>
            <div>
              <span className="text-[10px] text-slate-400 block">Average Dwell</span>
              <span className="font-semibold text-slate-900 tabular-nums">
                {activeResults?.averageDwellSeconds != null
                  ? `${Math.round(activeResults.averageDwellSeconds / 60)} min (${activeResults.averageDwellSeconds}s)`
                  : "—"}
              </span>
            </div>
          </div>
        </section>

        {/* Right Column: Ingestion Controls */}
        <section
          aria-label="CCTV upload and pipeline controls"
          className="lg:col-span-4 rounded-xl border border-[#e6e7e3] bg-white p-4.5 flex flex-col justify-between space-y-4"
        >
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-[#eeefec]">
              <h2 className="font-heading text-sm font-bold text-slate-900">
                FastAPI Video Ingestion
              </h2>
              <span className="text-[10px] font-mono text-slate-400">Max 200MB</span>
            </div>

            {/* Video Upload Dropzone */}
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragOver(e.dataTransfer.types.includes("Files"));
              }}
              onDragLeave={() => setIsDragOver(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`mt-3 flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-5 text-center cursor-pointer transition-colors ${
                isDragOver
                  ? "border-emerald-700 bg-emerald-50/50"
                  : selectedFile
                  ? "border-emerald-600 bg-emerald-50/30"
                  : "border-[#e6e7e3] hover:border-emerald-700 hover:bg-[#fafaf8]"
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".mp4,.webm,.mov,.avi,.png,.jpg,.jpeg"
                onChange={handleFileChange}
                className="sr-only"
                id="video-upload-input"
                aria-label="Upload video file"
              />

              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#f2f3ef] text-emerald-800 mb-2">
                <MaterialIcon name="upload" className="h-4 w-4" aria-hidden="true" />
              </div>
              <p className="text-xs font-bold text-slate-900">
                {selectedFile ? selectedFile.name : "Drop video or browse file"}
              </p>
              <p className="mt-0.5 text-[10px] text-slate-400">
                MP4, WebM, MOV, or AVI up to 200MB
              </p>

              {selectedFile && (
                <div className="mt-2 inline-flex items-center gap-1 rounded bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-900 tabular-nums">
                  <MaterialIcon name="check" className="h-3 w-3" aria-hidden="true" />
                  <span>{(selectedFile.size / (1024 * 1024)).toFixed(1)} MB ready</span>
                </div>
              )}
            </div>

            {validationError && (
              <div className="mt-2.5">
                <NoticeBanner
                  type="critical"
                  message={validationError}
                  onDismiss={() => setValidationError(null)}
                />
              </div>
            )}

            {/* Action Buttons */}
            <div className="mt-4 space-y-2.5">
              <button
                type="button"
                disabled={isUploading || isCurrentlyProcessing || !selectedFile}
                onClick={handleUploadAndProcess}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-900 px-3.5 py-2 text-xs font-bold text-white hover:bg-emerald-950 disabled:opacity-50 transition-colors shadow-2xs cursor-pointer"
              >
                {isUploading ? (
                  <>
                    <MaterialIcon name="refresh" className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                    <span>Uploading to FastAPI...</span>
                  </>
                ) : isCurrentlyProcessing ? (
                  <>
                    <MaterialIcon name="refresh" className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                    <span>Processing on Backend...</span>
                  </>
                ) : (
                  <>
                    <MaterialIcon name="play_arrow" className="h-3.5 w-3.5" filled aria-hidden="true" />
                    <span>Upload &amp; Process Video</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* CV Pipeline Integration Status */}
          <div className="rounded-lg bg-[#f8f8f6] border border-[#e6e7e3] p-3 text-[11px] text-slate-600 space-y-1.5">
            <div className="flex items-center justify-between font-bold text-slate-900">
              <span>FastAPI CV Integration</span>
              <span className="text-emerald-800 font-mono text-[10px]">
                {activeJob?.status === "done" ? "Results Ready" : isCurrentlyProcessing ? "Processing" : "Ready"}
              </span>
            </div>
            <p className="leading-snug text-slate-500">
              Dispatches binary video payloads using FormData to <code className="font-mono text-slate-700">POST /api/v1/videos</code>. Detections reflect actual backend inference.
            </p>
          </div>
        </section>
      </div>

      {/* Historical Ingestion Job Queue */}
      <section
        aria-label="Recent video processing jobs"
        className="rounded-xl border border-[#e6e7e3] bg-white p-4.5 space-y-3.5"
      >
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 pb-2.5 border-b border-[#eeefec]">
          <div>
            <h2 className="font-heading text-sm font-bold text-slate-900">
              Processing Job History
            </h2>
            <p className="text-xs text-slate-500">
              Video analytics jobs submitted to the FastAPI service
            </p>
          </div>
          <span className="text-xs font-semibold text-slate-500 tabular-nums">
            {jobs.length} total jobs
          </span>
        </div>

        {isLoadingJobs ? (
          <TableSkeleton rows={3} />
        ) : jobs.length === 0 ? (
          <EmptyState
            icon="videocam_off"
            title="No video jobs submitted"
            description="Upload a store video or CCTV recording above to run computer-vision detection."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs" aria-label="Processing jobs table">
              <thead className="border-b border-[#eeefec] bg-[#f8f8f6] text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                <tr>
                  <th className="px-3.5 py-2">Job ID</th>
                  <th className="px-3.5 py-2">File</th>
                  <th className="px-3.5 py-2">Ingested</th>
                  <th className="px-3.5 py-2">Status</th>
                  <th className="px-3.5 py-2 text-right">Frames</th>
                  <th className="px-3.5 py-2 text-right">Customers</th>
                  <th className="px-3.5 py-2 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#eeefec]">
                {jobs.map((job) => (
                  <tr
                    key={job.id}
                    onClick={() => setActiveJobId(job.id)}
                    className={`hover:bg-[#fafaf8] cursor-pointer transition-colors ${
                      activeJobId === job.id ? "bg-emerald-50/40" : ""
                    }`}
                  >
                    <td className="px-3.5 py-2.5 font-mono text-xs font-bold text-slate-900">
                      {job.id}
                    </td>
                    <td className="px-3.5 py-2.5 font-medium text-slate-800 flex items-center gap-2">
                      <MaterialIcon name="video_file" className="h-3.5 w-3.5 text-slate-400 shrink-0" aria-hidden="true" />
                      <span className="truncate max-w-[200px] sm:max-w-none">{job.file}</span>
                    </td>
                    <td className="px-3.5 py-2.5 text-slate-500">
                      {job.uploaded}
                    </td>
                    <td className="px-3.5 py-2.5">
                      <StatusBadge
                        variant={
                          job.status === "done"
                            ? "success"
                            : job.status === "processing"
                            ? "info"
                            : job.status === "queued"
                            ? "warning"
                            : "critical"
                        }
                        size="sm"
                        icon={
                          job.status === "done" ? (
                            <MaterialIcon name="check_circle" className="h-2.5 w-2.5" aria-hidden="true" />
                          ) : undefined
                        }
                      >
                        {job.status === "done"
                          ? "Completed"
                          : job.status === "processing"
                          ? "Processing"
                          : job.status === "queued"
                          ? "Queued"
                          : "Failed"}
                      </StatusBadge>
                    </td>
                    <td className="px-3.5 py-2.5 text-right font-mono text-slate-500 tabular-nums">
                      {job.frames ? job.frames.toLocaleString() : "—"}
                    </td>
                    <td className="px-3.5 py-2.5 text-right font-bold text-slate-900 tabular-nums">
                      {job.customersDetected ? job.customersDetected.toLocaleString() : "—"}
                    </td>
                    <td className="px-3.5 py-2.5 text-right">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setActiveJobId(job.id);
                        }}
                        className={`text-xs font-semibold px-2 py-0.5 rounded transition-colors ${
                          activeJobId === job.id
                            ? "bg-emerald-800 text-white"
                            : "text-slate-600 hover:text-slate-900 bg-slate-100"
                        }`}
                      >
                        {activeJobId === job.id ? "Selected" : "View"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
