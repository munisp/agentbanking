import { useState, useEffect, useMemo } from 'react';
import { useLocation } from 'wouter';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { useCurriculum } from '@/hooks/useCurriculum';
import { FileText, BookOpen, ExternalLink, Terminal, GraduationCap } from 'lucide-react';
import type { Lab, Module, Section } from '@/../../shared/types';

interface SearchDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface SearchResult {
  type: 'module' | 'section' | 'lab' | 'resource';
  title: string;
  description?: string;
  path: string;
  icon: any;
  badge?: string;
}

export default function SearchDialog({ open, onOpenChange }: SearchDialogProps) {
  const [query, setQuery] = useState('');
  const [, setLocation] = useLocation();
  const { data } = useCurriculum();

  // Reset query when dialog closes
  useEffect(() => {
    if (!open) {
      setQuery('');
    }
  }, [open]);

  // Build search index
  const searchResults = useMemo(() => {
    if (!data || !query.trim()) return [];

    const results: SearchResult[] = [];
    const searchTerm = query.toLowerCase();

    // Search modules
    data.modules.forEach((module: Module) => {
      if (
        module.title.toLowerCase().includes(searchTerm) ||
        module.description.toLowerCase().includes(searchTerm)
      ) {
        results.push({
          type: 'module',
          title: module.title,
          description: module.description,
          path: '/curriculum',
          icon: BookOpen,
          badge: 'Module',
        });
      }
    });

    // Search curriculum sections
    data.curriculumContent.sections.forEach((section: Section) => {
      if (
        section.title.toLowerCase().includes(searchTerm) ||
        section.content.toLowerCase().includes(searchTerm)
      ) {
        results.push({
          type: 'section',
          title: section.title,
          description: section.content.substring(0, 100) + '...',
          path: '/curriculum',
          icon: BookOpen,
          badge: 'Curriculum',
        });
      }
    });

    // Search infrastructure analysis
    data.infrastructureAnalysis.sections.forEach((section: Section) => {
      if (
        section.title.toLowerCase().includes(searchTerm) ||
        section.content.toLowerCase().includes(searchTerm)
      ) {
        results.push({
          type: 'section',
          title: section.title,
          description: section.content.substring(0, 100) + '...',
          path: '/infrastructure',
          icon: FileText,
          badge: 'Infrastructure',
        });
      }
    });

    // Search external resources
    data.externalResources.sections.forEach((section: Section) => {
      if (
        section.title.toLowerCase().includes(searchTerm) ||
        section.content.toLowerCase().includes(searchTerm)
      ) {
        results.push({
          type: 'resource',
          title: section.title,
          description: section.content.substring(0, 100) + '...',
          path: '/resources',
          icon: ExternalLink,
          badge: 'Resources',
        });
      }
    });

    // Search quick reference
    data.quickReference.sections.forEach((section: Section) => {
      if (
        section.title.toLowerCase().includes(searchTerm) ||
        section.content.toLowerCase().includes(searchTerm)
      ) {
        results.push({
          type: 'section',
          title: section.title,
          description: section.content.substring(0, 100) + '...',
          path: '/quick-reference',
          icon: Terminal,
          badge: 'Quick Ref',
        });
      }
    });

    // Search labs
    data.handsOnLabs.forEach((lab: Lab) => {
      if (
        lab.title.toLowerCase().includes(searchTerm) ||
        lab.description.toLowerCase().includes(searchTerm)
      ) {
        results.push({
          type: 'lab',
          title: lab.title,
          description: lab.description,
          path: '/labs',
          icon: GraduationCap,
          badge: `${lab.difficulty} Lab`,
        });
      }
    });

    return results.slice(0, 20); // Limit to 20 results
  }, [data, query]);

  const handleSelect = (path: string) => {
    setLocation(path);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] p-0">
        <DialogHeader className="px-6 pt-6 pb-4 border-b border-border">
          <DialogTitle>Search Curriculum</DialogTitle>
        </DialogHeader>
        
        <div className="px-6 py-4">
          <Input
            placeholder="Search for modules, topics, labs, or commands..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full"
            autoFocus
          />
        </div>

        <ScrollArea className="max-h-[400px] px-6 pb-6">
          {query.trim() === '' ? (
            <div className="text-center py-8 text-muted-foreground">
              <p>Start typing to search across all curriculum content</p>
              <p className="text-sm mt-2">
                Search modules, topics, labs, commands, and more
              </p>
            </div>
          ) : searchResults.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <p>No results found for "{query}"</p>
              <p className="text-sm mt-2">Try different keywords</p>
            </div>
          ) : (
            <div className="space-y-2">
              {searchResults.map((result, index) => {
                const Icon = result.icon;
                return (
                  <button
                    key={index}
                    onClick={() => handleSelect(result.path)}
                    className="w-full text-left p-3 rounded-lg hover:bg-muted transition-colors"
                  >
                    <div className="flex items-start space-x-3">
                      <Icon className="h-5 w-5 text-primary mt-0.5 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center space-x-2 mb-1">
                          <h4 className="font-medium text-sm">{result.title}</h4>
                          {result.badge && (
                            <Badge variant="secondary" className="text-xs">
                              {result.badge}
                            </Badge>
                          )}
                        </div>
                        {result.description && (
                          <p className="text-xs text-muted-foreground line-clamp-2">
                            {result.description}
                          </p>
                        )}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </ScrollArea>

        {searchResults.length > 0 && (
          <div className="px-6 py-3 border-t border-border text-xs text-muted-foreground">
            Found {searchResults.length} result{searchResults.length !== 1 ? 's' : ''}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
