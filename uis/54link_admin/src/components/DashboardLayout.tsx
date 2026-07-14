import { useState } from 'react';
import type { ReactNode } from 'react';
import { Link, useLocation } from 'wouter';
import {
  BookOpen,
  Home,
  FileText,
  ExternalLink,
  Terminal,
  GraduationCap,
  Menu,
  X,
  Moon,
  Sun,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useTheme } from '@/contexts/ThemeContext';
import { useProgress } from '@/contexts/ProgressContext';
import { useTenantBranding } from '@/contexts/TenantBrandingContext';
import { cn } from '@/lib/utils';
import GlobalSearch from '@/components/GlobalSearch';

interface DashboardLayoutProps {
  children: ReactNode;
}

const navigation = [
  { name: 'Home', href: '/', icon: Home },
  { name: 'Curriculum', href: '/curriculum', icon: BookOpen },
  { name: 'Infrastructure Analysis', href: '/infrastructure', icon: FileText },
  { name: 'External Resources', href: '/resources', icon: ExternalLink },
  { name: 'Quick Reference', href: '/quick-reference', icon: Terminal },
  { name: 'Hands-On Labs', href: '/labs', icon: GraduationCap },
];

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  const [location] = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { theme, toggleTheme } = useTheme();
  const { progress } = useProgress();
  const { name } = useTenantBranding();

  const completionPercentage = Math.round(
    (progress.completedModules.length / 8) * 100
  );

  return (
    <div className="min-h-screen bg-background">
      {/* Mobile sidebar backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed top-0 left-0 z-50 h-full w-64 bg-card border-r border-border transform transition-transform duration-200 ease-in-out lg:translate-x-0',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="flex items-center justify-between h-16 px-6 border-b border-border">
            <Link href="/">
              <div className="flex items-center space-x-2 cursor-pointer">
                <BookOpen className="h-6 w-6 text-primary" />
                <span className="font-semibold text-sm">Infrastructure Curriculum</span>
              </div>
            </Link>
            <Button
              variant="ghost"
              size="icon"
              className="lg:hidden"
              onClick={() => setSidebarOpen(false)}
            >
              <X className="h-5 w-5" />
            </Button>
          </div>

          {/* Progress indicator */}
          <div className="px-6 py-4 border-b border-border">
            <div className="text-xs text-muted-foreground mb-2">
              Overall Progress
            </div>
            <div className="flex items-center space-x-2">
              <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary transition-all duration-300"
                  style={{ width: `${completionPercentage}%` }}
                />
              </div>
              <span className="text-xs font-medium">{completionPercentage}%</span>
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              {progress.completedModules.length} of 8 modules completed
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex-1 px-3 py-4 overflow-y-auto">
            <ul className="space-y-1">
              {navigation.map((item) => {
                const Icon = item.icon;
                const isActive = location === item.href;
                return (
                  <li key={item.name}>
                    <Link href={item.href}>
                      <a
                        className={cn(
                          'flex items-center space-x-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                          isActive
                            ? 'bg-primary text-primary-foreground'
                            : 'text-foreground hover:bg-muted'
                        )}
                        onClick={() => setSidebarOpen(false)}
                      >
                        <Icon className="h-5 w-5" />
                        <span>{item.name}</span>
                      </a>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>

          {/* Footer */}
          <div className="px-6 py-4 border-t border-border">
            <div className="text-xs text-muted-foreground">
              <div className="font-medium mb-1">Platform v7.0</div>
              <div>Last Updated: Nov 4, 2025</div>
            </div>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="lg:pl-64">
        {/* Top bar */}
        <header className="sticky top-0 z-30 h-16 bg-card border-b border-border">
          <div className="flex items-center justify-between h-full px-4 sm:px-6">
            <div className="flex items-center space-x-4">
              <Button
                variant="ghost"
                size="icon"
                className="lg:hidden"
                onClick={() => setSidebarOpen(true)}
              >
                <Menu className="h-5 w-5" />
              </Button>
              <h1 className="text-lg font-semibold hidden sm:block">
                {name}
              </h1>
            </div>

            <div className="flex items-center space-x-2">
              <GlobalSearch />
              <Button variant="ghost" size="icon" onClick={toggleTheme}>
                {theme === 'dark' ? (
                  <Sun className="h-5 w-5" />
                ) : (
                  <Moon className="h-5 w-5" />
                )}
              </Button>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="min-h-[calc(100vh-4rem)]">{children}</main>
      </div>
    </div>
  );
}
