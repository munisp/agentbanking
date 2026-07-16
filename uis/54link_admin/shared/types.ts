export interface CurriculumData {
  metadata: {
    title: string;
    version: string;
    lastUpdated: string;
    platformVersion: string;
  };
  overview: {
    title: string;
    content: string;
    stats: {
      totalServices: number;
      testCoverage: string;
      apisixRoutes: number;
      daprConfigs: number;
      temporalWorkflows: number;
      keycloakClients: number;
      k8sDeployments: number;
      dockerfiles: number;
      databaseModels: number;
    };
  };
  modules: Module[];
  infrastructureAnalysis: ContentSection;
  curriculumContent: ContentSection;
  externalResources: ContentSection;
  quickReference: ContentSection;
  learningPath: LearningPath;
  handsOnLabs: Lab[];
}

export interface Module {
  id: string;
  title: string;
  icon: string;
  description: string;
  duration: string;
  content: string;
  externalResources: any[];
}

export interface ContentSection {
  title: string;
  content: string;
  sections: Section[];
}

export interface Section {
  title: string;
  content: string;
  level: number;
}

export interface LearningPath {
  title: string;
  months: Month[];
}

export interface Month {
  month: number;
  title: string;
  topics: string[];
}

export interface Lab {
  id: string;
  title: string;
  description: string;
  difficulty: string;
  estimatedTime: string;
}

export interface ProgressState {
  completedModules: string[];
  completedLabs: string[];
  lastVisited: string;
  bookmarks: string[];
}
