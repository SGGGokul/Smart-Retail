export type JobStatus = "queued" | "processing" | "done" | "failed";

export interface VideoDetectionBox {
  id: string;
  label: string;
  confidence: number;
  box: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
}

export interface VideoJob {
  id: string;
  file: string;
  uploaded: string;
  status: JobStatus;
  frames: number;
  customersDetected: number;
  durationSeconds?: number;
  fps?: number;
  processedAt?: string;
}

export interface VideoUploadResponse {
  jobId: string;
  filename: string;
  status: JobStatus;
  message: string;
}

export interface VideoResultsResponse {
  jobId: string;
  status: JobStatus;
  totalFrames: number;
  customersDetected: number;
  peakCount: number;
  averageDwellSeconds: number;
  detections: VideoDetectionBox[];
}
