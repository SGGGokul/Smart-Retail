/**
 * Centralized API endpoints conforming to API_CONTRACT.md
 */
export const ENDPOINTS = {
  // Health
  HEALTH: "/health",

  // Analytics
  ANALYTICS_SUMMARY: "/api/v1/analytics/summary",
  ANALYTICS_TRAFFIC: "/api/v1/analytics/traffic",
  ANALYTICS_DWELL_TIME: "/api/v1/analytics/dwell-time",
  ANALYTICS_QUEUES: "/api/v1/analytics/queues",

  // Customer Journey & Visitor Intelligence
  CUSTOMER_JOURNEY_METRICS: "/api/v1/customer-journey/metrics",
  CUSTOMER_JOURNEY_DAILY_VISITORS: "/api/v1/customer-journey/daily-visitors",
  CUSTOMER_JOURNEY_VISITS: "/api/v1/customer-journey/visits",

  // Shelf Monitoring & Stock Metrics
  SHELVES: "/api/v1/shelves",
  SHELVES_METRICS: "/api/v1/shelves/metrics",
  SHELVES_DETECT: "/api/v1/shelves/detect",

  // Unified Retail Events Timeline
  EVENTS_TIMELINE: "/api/v1/events/timeline",

  // Image Detection
  IMAGES_DETECT: "/api/v1/images/detect",

  // Alerts
  ALERTS: "/api/v1/alerts",
  ALERT_BY_ID: (id: string) => `/api/v1/alerts/${encodeURIComponent(id)}`,

  // Video Processing & Computer Vision
  VIDEOS: "/api/v1/videos",
  VIDEO_BY_ID: (id: string) => `/api/v1/videos/${encodeURIComponent(id)}`,
  VIDEO_RESULTS: (id: string) => `/api/v1/videos/${encodeURIComponent(id)}/results`,

  // AI Assistant
  ASSISTANT_CHAT: "/api/v1/assistant/chat",
} as const;
