import * as mock from './mockData';

// Helper to simulate network latency
const delay = (ms = 500) => new Promise(resolve => setTimeout(resolve, ms));

const api = {
  getDashboardSummary: async () => {
    await delay();
    return mock.mockDashboardSummary;
  },
  
  resolveDashboardIssues: async () => {
    await delay();
    return { success: true };
  },

  uploadSpecification: async (formData) => {
    await delay(1000);
    return { id: "doc-mock-1", status: "ready" };
  },

  uploadSubmittal: async (formData) => {
    await delay(1000);
    return { id: "doc-mock-2", status: "ready" };
  },

  getDocumentStatus: async (docId) => {
    await delay(200);
    return { status: "ready" };
  },

  pollUntilReady: async (docId, onProgress) => {
    await delay(1500);
    if(onProgress) onProgress({status: "ready"});
    return { status: "ready" };
  },

  getDocuments: async (projectId) => {
    await delay();
    return mock.mockDocumentsResponse;
  },

  deleteDocument: async (docId) => {
    await delay();
    return { success: true };
  },

  getEquipmentItems: async () => {
    await delay();
    return mock.mockEquipment;
  },

  runComplianceCheck: async (poId) => {
    await delay(2000);
    return mock.mockComplianceResults;
  },

  getComplianceResults: async (poId) => {
    await delay();
    return mock.mockComplianceResults;
  },

  getNcrs: async (filters = {}) => {
    await delay();
    return mock.mockNcrsResponse;
  },

  getNcrDetail: async (ncrId) => {
    await delay();
    return mock.mockNcrDetail;
  },

  importSchedule: async (formData) => {
    await delay(1000);
    return { success: true };
  },

  analyzeSchedule: async (projectId) => {
    await delay(1500);
    return mock.mockDelayComparison;
  },

  getScheduleTasks: async (projectId) => {
    await delay();
    return mock.mockScheduleTasksResponse;
  },

  getScheduleRisks: async (projectId) => {
    await delay();
    return mock.mockScheduleRisksResponse;
  },

  exportProjectReport: async (projectId) => {
    await delay();
    return "Mock Report Content";
  },

  queryRFI: async (query) => {
    await delay(1500);
    return {
      answer: "This is a mocked answer from the static frontend.",
      sources: []
    };
  },

  getRFIs: async () => {
    await delay();
    return mock.mockRFIs;
  },

  getPurchaseOrders: async () => {
    await delay();
    return mock.mockDashboardSummary.purchase_orders;
  },

  getProjects: async () => {
    await delay();
    return mock.mockProjects;
  },

  createProject: async (projectData) => {
    await delay();
    return { id: "proj-new", ...projectData, status: "active" };
  },

  updateProjectStatus: async (projectId, status) => {
    await delay();
    return { success: true };
  },

  deleteProject: async (projectId) => {
    await delay();
    return { success: true };
  },

  getOpenProjects: async () => {
    await delay();
    return mock.mockProjects;
  },

  registerVendor: async (vendorData) => {
    await delay();
    return { success: true };
  },

  loginVendor: async (email, password) => {
    await delay();
    return { success: true, token: "mock-token" };
  },

  createBid: async (bidData) => {
    await delay();
    return { success: true };
  },

  getBids: async (projectId) => {
    await delay();
    return mock.mockBids;
  },

  updateBidStatus: async (bidId, status) => {
    await delay();
    return { success: true };
  },

  getBidRecommendations: async (projectId) => {
    await delay();
    return [ mock.mockBids[0] ];
  },

  uploadGeneral: async (formData) => {
    await delay();
    return { success: true };
  },

  uploadIntegrationDocument: async (file, standardName) => {
    await delay();
    return { success: true };
  },

  getCommissioningTasks: async () => {
    await delay();
    return mock.mockCommissioningTasks;
  },

  generateCommissioningChecklist: async (taskId) => {
    await delay();
    return { success: true };
  },

  runCommissioningStep: async (taskId, stepNumber, actualValue, checkedBy) => {
    await delay();
    return { success: true };
  },

  getCommissioningRecords: async () => {
    await delay();
    return mock.mockCommissioningRecords;
  },

  getSupplyChainShipments: async () => {
    await delay();
    return mock.mockSupplyChainShipments;
  },

  getSupplyChainAlerts: async () => {
    await delay();
    return mock.mockSupplyChainAlerts;
  },

  getSupplyChainMap: async () => {
    await delay();
    return { locations: [] };
  },

  triggerSupplyChainShock: async (payload) => {
    await delay();
    return { success: true, message: "Mock shock triggered" };
  },

  triggerSupplyChainShockLangGraph: async (payload) => {
    await delay();
    return { success: true, message: "Mock langgraph shock triggered" };
  },

  getDelayComparison: async () => {
    await delay();
    return mock.mockDelayComparison;
  }
};

export default api;
