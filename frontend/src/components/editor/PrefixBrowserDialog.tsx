import { useState, useEffect, useCallback } from 'react';
import { Folder, ChevronRight, Loader2, Search, X } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { listS3Prefixes } from '@/api';
import type { S3ConnectorData } from '@/types';

interface PrefixBrowserDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  s3Data: S3ConnectorData;
  currentPrefix: string;
  onSelect: (prefix: string) => void;
}

export function PrefixBrowserDialog({
  open,
  onOpenChange,
  s3Data,
  currentPrefix,
  onSelect,
}: PrefixBrowserDialogProps) {
  const [prefixes, setPrefixes] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentPath, setCurrentPath] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedPrefix, setSelectedPrefix] = useState<string>(currentPrefix);

  // Check if credentials are filled
  const hasCredentials = useCallback(() => {
    if (s3Data.providerType === 'cloudflare') {
      return !!(s3Data.accountId && s3Data.accessKey && s3Data.secretKey && s3Data.bucket);
    } else if (['aws', 'wasabi', 'digitalocean', 'hetzner'].includes(s3Data.providerType)) {
      return !!(s3Data.accessKey && s3Data.secretKey && s3Data.bucket);
    } else if (s3Data.providerType === 'backblaze') {
      return !!(s3Data.applicationKeyId && s3Data.applicationKey && s3Data.bucketName);
    } else if (s3Data.providerType === 'gcs') {
      return !!(s3Data.projectId && s3Data.bucketName && s3Data.credentialsJson);
    }
    return false;
  }, [s3Data]);

  // Fetch prefixes for current path
  const fetchPrefixes = useCallback(
    async (path: string) => {
      if (!hasCredentials()) {
        setPrefixes([]);
        return;
      }

      setLoading(true);
      setError(null);

      try {
        const fetchedPrefixes = await listS3Prefixes(s3Data, path);
        setPrefixes(fetchedPrefixes);
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to load prefixes';
        setError(errorMessage);
        setPrefixes([]);
      } finally {
        setLoading(false);
      }
    },
    [s3Data, hasCredentials]
  );

  // Initialize with current prefix path
  useEffect(() => {
    if (open) {
      setCurrentPath(currentPrefix || '');
      setSelectedPrefix(currentPrefix || '');
      setSearchQuery('');
      if (hasCredentials()) {
        fetchPrefixes(currentPrefix || '');
      }
    }
  }, [open, currentPrefix, hasCredentials, fetchPrefixes]);

  // Navigate into a folder
  const handleNavigate = (prefix: string) => {
    setCurrentPath(prefix);
    setSelectedPrefix(prefix);
    setSearchQuery('');
    fetchPrefixes(prefix);
  };

  // Navigate up using breadcrumb
  const handleBreadcrumbClick = (path: string) => {
    setCurrentPath(path);
    setSelectedPrefix(path);
    setSearchQuery('');
    fetchPrefixes(path);
  };

  // Build breadcrumb segments
  const breadcrumbSegments = useCallback(() => {
    if (!currentPath) return [{ path: '', label: 'Root' }];
    
    const parts = currentPath.split('/').filter(Boolean);
    const segments = [{ path: '', label: 'Root' }];
    
    let accumulatedPath = '';
    for (const part of parts) {
      accumulatedPath += part + '/';
      segments.push({ path: accumulatedPath, label: part });
    }
    
    return segments;
  }, [currentPath]);

  // Filter prefixes based on search
  const filteredPrefixes = searchQuery
    ? prefixes.filter((prefix) =>
        prefix.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : prefixes;

  // Get relative name for display
  const getRelativeName = (prefix: string) => {
    if (!currentPath) return prefix;
    return prefix.replace(currentPath, '');
  };

  const handleSelect = () => {
    onSelect(selectedPrefix);
    onOpenChange(false);
  };

  const segments = breadcrumbSegments();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Select Prefix / Path</DialogTitle>
          <DialogDescription>
            Browse and select a folder path from your S3 bucket
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-hidden flex flex-col space-y-4">
          {/* Breadcrumb Navigation */}
          <div className="flex items-center gap-1 text-sm flex-wrap">
            {segments.map((segment, index) => (
              <div key={segment.path} className="flex items-center gap-1">
                {index > 0 && <ChevronRight className="h-4 w-4 text-gray-400" />}
                <button
                  type="button"
                  onClick={() => handleBreadcrumbClick(segment.path)}
                  className={cn(
                    'px-2 py-1 rounded hover:bg-gray-100 transition-colors',
                    segment.path === currentPath && 'bg-blue-50 text-blue-600 font-medium'
                  )}
                >
                  {segment.label}
                </button>
              </div>
            ))}
          </div>

          {/* Search Bar */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search folders..."
              className={cn(
                "pl-9 pr-3",
                searchQuery && "pr-9"
              )}
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>

          {/* Prefix List */}
          <div className="flex-1 overflow-auto border border-gray-200 rounded-md">
            {loading && (
              <div className="flex flex-col items-center justify-center p-8">
                <Loader2 className="h-6 w-6 animate-spin text-gray-400 mb-2" />
                <p className="text-sm text-gray-500">Loading folders...</p>
              </div>
            )}

            {error && !loading && (
              <div className="p-6 text-center">
                <p className="text-sm font-medium text-red-600 mb-1">Error loading folders</p>
                <p className="text-xs text-red-500 mb-4">{error}</p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => fetchPrefixes(currentPath)}
                >
                  Retry
                </Button>
              </div>
            )}

            {!loading && !error && filteredPrefixes.length === 0 && (
              <div className="p-6 text-center text-sm text-gray-500">
                {searchQuery ? 'No folders match your search' : 'No folders found at this level'}
              </div>
            )}

            {!loading && !error && filteredPrefixes.length > 0 && (
              <div className="divide-y divide-gray-100">
                {/* Root option */}
                {!currentPath && (
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedPrefix('');
                      handleNavigate('');
                    }}
                    className={cn(
                      'w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 transition-colors text-left',
                      selectedPrefix === '' && 'bg-blue-50 border-l-2 border-blue-600'
                    )}
                  >
                    <Folder className="h-5 w-5 text-gray-400 flex-shrink-0" />
                    <span className="text-sm font-medium">Root (/)</span>
                  </button>
                )}

                {filteredPrefixes.map((prefix) => {
                  const relativeName = getRelativeName(prefix);
                  const isSelected = selectedPrefix === prefix;
                  
                  return (
                    <button
                      key={prefix}
                      type="button"
                      onClick={() => {
                        setSelectedPrefix(prefix);
                        handleNavigate(prefix);
                      }}
                      className={cn(
                        'w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 transition-colors text-left',
                        isSelected && 'bg-blue-50 border-l-2 border-blue-600'
                      )}
                    >
                      <Folder className="h-5 w-5 text-gray-400 flex-shrink-0" />
                      <span className="text-sm flex-1">{relativeName}</span>
                      <ChevronRight className="h-4 w-4 text-gray-300 flex-shrink-0" />
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Current Selection Display */}
          <div className="px-3 py-2 bg-gray-50 rounded-md border border-gray-200">
            <p className="text-xs text-gray-500 mb-1">Selected path:</p>
            <p className="text-sm font-mono text-gray-900">
              {selectedPrefix || '(root)'}
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSelect} disabled={loading}>
            Select
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

