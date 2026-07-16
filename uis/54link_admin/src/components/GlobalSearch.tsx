import { Search, Home, FileText, X } from 'lucide-react';
import { useState, useEffect } from 'react';
import { useLocation } from 'wouter';

interface SearchResult {
  id: string;
  type: 'page' | 'section';
  title: string;
  subtitle: string;
  path: string;
  keywords: string[];
}

// Real platform pages indexed for search - matches sidebar navigation
const platformPages: SearchResult[] = [
  {
    id: 'home',
    type: 'page',
    title: 'Home',
    subtitle: 'Dashboard Overview',
    path: '/',
    keywords: ['home', 'dashboard', 'overview', 'main', 'start'],
  },
  {
    id: 'curriculum',
    type: 'page',
    title: 'Curriculum',
    subtitle: 'Learning Modules & Content',
    path: '/curriculum',
    keywords: ['curriculum', 'learning', 'modules', 'courses', 'training', 'education', 'lessons'],
  },
  {
    id: 'infrastructure',
    type: 'page',
    title: 'Infrastructure Analysis',
    subtitle: 'System Architecture & Resources',
    path: '/infrastructure',
    keywords: ['infrastructure', 'architecture', 'analysis', 'system', 'deployment', 'setup', 'configuration'],
  },
  {
    id: 'resources',
    type: 'page',
    title: 'External Resources',
    subtitle: 'Documentation & Links',
    path: '/resources',
    keywords: ['resources', 'documentation', 'external', 'links', 'guides', 'docs', 'references'],
  },
  {
    id: 'quick-ref',
    type: 'page',
    title: 'Quick Reference',
    subtitle: 'Command Line Reference',
    path: '/quick-reference',
    keywords: ['quick', 'reference', 'commands', 'cli', 'terminal', 'shortcuts', 'cheatsheet'],
  },
  {
    id: 'labs',
    type: 'page',
    title: 'Hands-On Labs',
    subtitle: 'Interactive Learning Exercises',
    path: '/labs',
    keywords: ['labs', 'hands-on', 'exercises', 'practice', 'interactive', 'learning', 'training'],
  },
];


export default function GlobalSearch() {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const [, setLocation] = useLocation();

  useEffect(() => {
    if (query.length > 0) {
      const searchTerm = query.toLowerCase();
      const filtered = platformPages.filter(result =>
        result.title.toLowerCase().includes(searchTerm) ||
        result.subtitle.toLowerCase().includes(searchTerm) ||
        result.keywords.some(keyword => keyword.includes(searchTerm))
      );
      setResults(filtered);
      setSelectedIndex(-1);
    } else {
      setResults([]);
      setSelectedIndex(-1);
    }
  }, [query]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsOpen(true);
      }
      if (e.key === 'Escape') {
        setIsOpen(false);
        setSelectedIndex(-1);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleSearchKeyDown = (e: React.KeyboardEvent) => {
    if (results.length === 0) return;

    switch (e.key) {
      case 'ArrowDown': {
        e.preventDefault();
        setSelectedIndex(prev => 
          prev < results.length - 1 ? prev + 1 : 0
        );
        break;
      }
      case 'ArrowUp': {
        e.preventDefault();
        setSelectedIndex(prev => 
          prev > 0 ? prev - 1 : results.length - 1
        );
        break;
      }
      case 'Enter': {
        e.preventDefault();
        if (selectedIndex >= 0 && selectedIndex < results.length) {
          handleSelect(results[selectedIndex]);
        }
        break;
      }
    }
  };

  const getIcon = (type: string) => {
    switch (type) {
      case 'page': return <Home className="w-5 h-5 text-blue-600" />;
      case 'section': return <FileText className="w-5 h-5 text-purple-600" />;
      default: return <Search className="w-5 h-5 text-gray-600" />;
    }
  };

  const handleSelect = (result: SearchResult) => {
    setLocation(result.path);
    setIsOpen(false);
    setQuery('');
  };

  return (
    <>
      {/* Search Button */}
      <button
        onClick={() => setIsOpen(true)}
        className="flex items-center gap-2 px-4 py-2 bg-gray-100 dark:bg-slate-700 hover:bg-gray-200 dark:hover:bg-slate-600 rounded-lg transition-colors text-gray-600 dark:text-gray-400"
      >
        <Search className="w-5 h-5" />
        <span className="text-sm">Search...</span>
        <kbd className="hidden md:inline-block px-2 py-1 text-xs bg-white dark:bg-slate-800 border border-gray-300 dark:border-slate-600 rounded">
          ⌘K
        </kbd>
      </button>

      {/* Search Modal */}
      {isOpen && (
        <>
          {/* Backdrop */}
          <div 
            className="fixed inset-0 bg-black/50 z-50" 
            onClick={() => setIsOpen(false)}
          />
          
          {/* Search Panel */}
          <div className="fixed top-20 left-1/2 transform -translate-x-1/2 w-full max-w-2xl z-50">
            <div className="bg-white dark:bg-slate-800 rounded-xl shadow-2xl border border-gray-200 dark:border-slate-700 overflow-hidden">
              {/* Search Input */}
              <div className="flex items-center gap-3 p-4 border-b border-gray-200 dark:border-slate-700">
                <Search className="w-6 h-6 text-gray-400" />
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={handleSearchKeyDown}
                  placeholder="Search banks, features, transactions..."
                  className="flex-1 bg-transparent text-gray-900 dark:text-white placeholder-gray-400 outline-none text-lg"
                  autoFocus
                />
                <button
                  onClick={() => setIsOpen(false)}
                  className="p-1 hover:bg-gray-100 dark:hover:bg-slate-700 rounded"
                >
                  <X className="w-5 h-5 text-gray-600 dark:text-gray-400" />
                </button>
              </div>

              {/* Results */}
              {results.length > 0 ? (
                <div className="max-h-96 overflow-y-auto p-2">
                  {results.map((result, index) => (
                    <button
                      key={result.id}
                      onClick={() => handleSelect(result)}
                      className={`w-full flex items-center gap-3 p-3 rounded-lg transition-colors text-left ${
                        index === selectedIndex
                          ? 'bg-blue-100 dark:bg-slate-600'
                          : 'hover:bg-gray-100 dark:hover:bg-slate-700'
                      }`}
                    >
                      <div className="p-2 bg-gray-100 dark:bg-slate-700 rounded-lg">
                        {getIcon(result.type)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="font-semibold text-gray-900 dark:text-white">
                          {result.title}
                        </div>
                        <div className="text-sm text-gray-600 dark:text-gray-400 truncate">
                          {result.subtitle}
                        </div>
                      </div>
                      <div className="text-xs text-gray-400 uppercase">
                        {result.type}
                      </div>
                    </button>
                  ))}
                </div>
              ) : query.length > 0 ? (
                <div className="p-8 text-center text-gray-500 dark:text-gray-400">
                  No results found for "{query}"
                </div>
              ) : (
                <div className="p-8 text-center text-gray-500 dark:text-gray-400">
                  <p className="mb-2">Start typing to search</p>
                  <p className="text-sm">Search across banks, features, and transactions</p>
                </div>
              )}

              {/* Footer */}
              <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200 dark:border-slate-700 text-xs text-gray-500 dark:text-gray-400">
                <div className="flex gap-4">
                  <span><kbd className="px-2 py-1 bg-gray-100 dark:bg-slate-700 rounded">↑↓</kbd> Navigate</span>
                  <span><kbd className="px-2 py-1 bg-gray-100 dark:bg-slate-700 rounded">Enter</kbd> Select</span>
                  <span><kbd className="px-2 py-1 bg-gray-100 dark:bg-slate-700 rounded">Esc</kbd> Close</span>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </>
  );
}
