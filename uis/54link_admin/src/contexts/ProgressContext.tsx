import { createContext, useContext, useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import type { ProgressState } from '@/../../shared/types';

interface ProgressContextType {
  progress: ProgressState;
  markModuleComplete: (moduleId: string) => void;
  markLabComplete: (labId: string) => void;
  addBookmark: (path: string) => void;
  removeBookmark: (path: string) => void;
  isModuleComplete: (moduleId: string) => boolean;
  isLabComplete: (labId: string) => boolean;
  isBookmarked: (path: string) => boolean;
}

const ProgressContext = createContext<ProgressContextType | undefined>(undefined);

const STORAGE_KEY = 'infrastructure-curriculum-progress';

const defaultProgress: ProgressState = {
  completedModules: [],
  completedLabs: [],
  lastVisited: '/',
  bookmarks: [],
};

export function ProgressProvider({ children }: { children: ReactNode }) {
  const [progress, setProgress] = useState<ProgressState>(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : defaultProgress;
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(progress));
  }, [progress]);

  const markModuleComplete = (moduleId: string) => {
    setProgress(prev => ({
      ...prev,
      completedModules: prev.completedModules.includes(moduleId)
        ? prev.completedModules
        : [...prev.completedModules, moduleId],
    }));
  };

  const markLabComplete = (labId: string) => {
    setProgress(prev => ({
      ...prev,
      completedLabs: prev.completedLabs.includes(labId)
        ? prev.completedLabs
        : [...prev.completedLabs, labId],
    }));
  };

  const addBookmark = (path: string) => {
    setProgress(prev => ({
      ...prev,
      bookmarks: prev.bookmarks.includes(path)
        ? prev.bookmarks
        : [...prev.bookmarks, path],
    }));
  };

  const removeBookmark = (path: string) => {
    setProgress(prev => ({
      ...prev,
      bookmarks: prev.bookmarks.filter(b => b !== path),
    }));
  };

  const isModuleComplete = (moduleId: string) => {
    return progress.completedModules.includes(moduleId);
  };

  const isLabComplete = (labId: string) => {
    return progress.completedLabs.includes(labId);
  };

  const isBookmarked = (path: string) => {
    return progress.bookmarks.includes(path);
  };

  return (
    <ProgressContext.Provider
      value={{
        progress,
        markModuleComplete,
        markLabComplete,
        addBookmark,
        removeBookmark,
        isModuleComplete,
        isLabComplete,
        isBookmarked,
      }}
    >
      {children}
    </ProgressContext.Provider>
  );
}

export function useProgress() {
  const context = useContext(ProgressContext);
  if (!context) {
    throw new Error('useProgress must be used within ProgressProvider');
  }
  return context;
}
