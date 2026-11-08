export * from "./client";
export * from "./endpoints";
export * from "./system";
export * from "./dashboard";
export * from "./customer-analytics";
export * from "./video-analytics";
export * from "./shelf-monitoring";
export * from "./alerts";
export * from "./reports";
export * from "./assistant";

import * as systemApi from "./system";
import * as dashboardApi from "./dashboard";
import * as customerApi from "./customer-analytics";
import * as videoApi from "./video-analytics";
import * as shelfApi from "./shelf-monitoring";
import * as alertApi from "./alerts";
import * as reportApi from "./reports";
import * as assistantApi from "./assistant";

export const retailApi = {
  checkHealth: systemApi.checkHealth,
  analytics: {
    getSummary: dashboardApi.getDashboardSummary,
    getTraffic: customerApi.getCustomerTraffic,
    getDwellTime: customerApi.getCustomerDwellTime,
    getQueues: customerApi.getCheckoutQueues,
  },
  shelves: {
    list: shelfApi.listShelves,
    getById: shelfApi.getShelfById,
  },
  alerts: {
    list: alertApi.listAlerts,
    update: alertApi.updateAlert,
  },
  videos: {
    upload: videoApi.uploadVideo,
    getJob: videoApi.getVideoJob,
    getResults: videoApi.getVideoResults,
    list: videoApi.listVideoJobs,
  },
  assistant: {
    chat: assistantApi.sendChatMessage,
  },
  reports: {
    getBundle: reportApi.getReportBundle,
  },
};

export default retailApi;
