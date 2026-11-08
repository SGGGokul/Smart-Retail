import { apiRequest } from "./client";
import { ENDPOINTS } from "./endpoints";
import type {
  VideoUploadResponse,
  VideoJob,
  VideoResultsResponse,
  ImageDetectionResponse,
} from "@/types/detection";

/**
 * Uploads a CCTV or store video file for asynchronous detection and tracking.
 * POST /api/v1/videos
 */
export async function uploadVideo(file: File, signal?: AbortSignal): Promise<VideoUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  return apiRequest<VideoUploadResponse>(ENDPOINTS.VIDEOS, {
    method: "POST",
    body: formData,
    signal,
  });
}

/**
 * Checks the processing status of a video job.
 * GET /api/v1/videos/{id}
 */
export async function getVideoJob(id: string, signal?: AbortSignal): Promise<VideoJob> {
  return apiRequest<VideoJob>(ENDPOINTS.VIDEO_BY_ID(id), { signal });
}

/**
 * Fetches detailed detection bounding boxes, customer counts, and metrics for a completed video job.
 * GET /api/v1/videos/{id}/results
 */
export async function getVideoResults(id: string, signal?: AbortSignal): Promise<VideoResultsResponse> {
  return apiRequest<VideoResultsResponse>(ENDPOINTS.VIDEO_RESULTS(id), { signal });
}

/**
 * Attempts to list historical video processing jobs.
 * NOTE: If the backend does not expose GET /api/v1/videos, callers can catch
 * and use session-cached jobs.
 */
export async function listVideoJobs(signal?: AbortSignal): Promise<VideoJob[]> {
  const res = await apiRequest<VideoJob[] | { jobs: VideoJob[] }>(ENDPOINTS.VIDEOS, { signal });
  if (Array.isArray(res)) return res;
  if (res && Array.isArray((res as { jobs: VideoJob[] }).jobs)) return (res as { jobs: VideoJob[] }).jobs;
  return [];
}

/**
 * Uploads a retail or shelf image for YOLO object and shelf detection.
 * POST /api/v1/images/detect
 */
export async function detectImage(
  file: File,
  confidence: number = 0.25,
  signal?: AbortSignal
): Promise<ImageDetectionResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const endpoint = `${ENDPOINTS.IMAGES_DETECT}?confidence=${confidence}`;
  return apiRequest<ImageDetectionResponse>(endpoint, {
    method: "POST",
    body: formData,
    signal,
  });
}

