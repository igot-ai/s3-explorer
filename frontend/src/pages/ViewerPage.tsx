import { useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Cloud, FolderOpen, CheckCircle, XCircle, Clock, FileText, Folder } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useRoutineStore } from '@/store';
import type { Node, IngestionFileResult } from '@/types';

export function ViewerPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { routines, lastExecutionResult } = useRoutineStore();

  const routine = routines.find((r) => r.id === id);

  useEffect(() => {
    if (!routine) {
      navigate('/');
    }
  }, [routine, navigate]);

  if (!routine) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-gray-500">Loading...</p>
      </div>
    );
  }

  const nodeConfig = {
    's3-connector': { icon: Cloud, color: 'border-orange-400 bg-orange-50', iconColor: 'text-orange-500' },
    'collection': { icon: FolderOpen, color: 'border-emerald-400 bg-emerald-50', iconColor: 'text-emerald-500' },
  };

  const getNodeName = (node: Node) => {
    return node.data.name || node.type;
  };

  // Sort nodes by connection order
  const getOrderedNodes = () => {
    const nodes = [...routine.nodes];
    const connections = routine.connections;
    const ordered: Node[] = [];
    const visited = new Set<string>();

    // Find starting nodes (no incoming connections)
    const hasIncoming = new Set(connections.map((c) => c.to));
    let current = nodes.find((n) => !hasIncoming.has(n.id));

    while (current && !visited.has(current.id)) {
      ordered.push(current);
      visited.add(current.id);
      const nextConnection = connections.find((c) => c.from === current!.id);
      current = nextConnection ? nodes.find((n) => n.id === nextConnection.to) : undefined;
    }

    // Add any remaining unconnected nodes
    nodes.forEach((n) => {
      if (!visited.has(n.id)) ordered.push(n);
    });

    return ordered;
  };

  // Get all files from execution result
  const getAllFiles = (): IngestionFileResult[] => {
    if (!lastExecutionResult?.folders) return [];
    return lastExecutionResult.folders.flatMap((folder) => folder.files);
  };

  const files = getAllFiles();

  // Calculate stats from execution result
  const stats = lastExecutionResult ? {
    totalFiles: lastExecutionResult.total_files,
    successful: lastExecutionResult.successful,
    failed: lastExecutionResult.failed,
    successRate: lastExecutionResult.success_rate,
    executionTime: lastExecutionResult.execution_time,
    totalFolders: lastExecutionResult.total_folders,
  } : null;

  const getFileName = (path: string) => {
    const parts = path.split('/');
    return parts[parts.length - 1];
  };

  const getCatalogName = (catalogId: string | null) => {
    if (!catalogId) return 'Unclassified';
    // Find the collection node with this catalog ID
    const collectionNode = routine.nodes.find((n) => {
      if (n.data.type !== 'collection') return false;
      return (n.data as { catalogId?: string }).catalogId === catalogId;
    });
    return collectionNode?.data.name || catalogId;
  };

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Top Bar */}
      <header className="bg-white border-b px-4 py-3 flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate('/')}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div>
          <h1 className="font-semibold">{routine.name}</h1>
          <p className="text-sm text-gray-500">Project: {routine.projectName}</p>
        </div>
        <span className="ml-auto inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
          Completed
        </span>
      </header>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Pipeline + Results */}
        <div className="flex-1 p-6 overflow-auto">
          {/* Pipeline View */}
          <h2 className="text-sm font-medium text-gray-500 mb-4">Pipeline</h2>
          <div className="flex items-center gap-6 flex-wrap mb-8">
            {getOrderedNodes().map((node, index) => {
              const config = nodeConfig[node.type];
              const Icon = config.icon;
              
              return (
                <div key={node.id} className="flex items-center gap-6">
                  <div className={`w-56 rounded-xl border-2 ${config.color} p-4`}>
                    <div className="flex items-center gap-3">
                      <Icon className={`w-5 h-5 ${config.iconColor}`} />
                      <span className="text-base font-medium truncate">{getNodeName(node)}</span>
                    </div>
                    <p className="text-sm text-gray-500 mt-1.5">{node.type.replace('-', ' ')}</p>
                  </div>
                  
                  {index < getOrderedNodes().length - 1 && (
                    <div className="w-10 h-0.5 bg-gray-300" />
                  )}
                </div>
              );
            })}
          </div>

          {/* Results Section */}
          {lastExecutionResult && (
            <>
              <h2 className="text-sm font-medium text-gray-500 mb-4">Processed Files</h2>
              
              {/* Folder-based view */}
              {lastExecutionResult.folders.map((folder) => (
                <div key={folder.folder_path} className="mb-6">
                  <div className="flex items-center gap-2 mb-3">
                    <Folder className="w-4 h-4 text-gray-500" />
                    <span className="text-sm font-medium text-gray-700">{folder.folder_path}</span>
                    <span className="text-xs text-gray-500">
                      ({folder.successful_count} successful, {folder.failed_count} failed)
                    </span>
                  </div>
                  
                  <div className="bg-white rounded-lg border divide-y">
                    {folder.files.map((file, idx) => (
                      <div
                        key={`${file.source_path}-${idx}`}
                        className="flex items-start gap-3 p-3 hover:bg-gray-50"
                      >
                        {file.status === 'uploaded' ? (
                          <CheckCircle className="w-5 h-5 text-green-500 mt-0.5 flex-shrink-0" />
                        ) : (
                          <XCircle className="w-5 h-5 text-red-500 mt-0.5 flex-shrink-0" />
                        )}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <FileText className="w-4 h-4 text-gray-400" />
                            <p className="text-sm font-medium truncate" title={file.source_path}>
                              {getFileName(file.source_path)}
                            </p>
                          </div>
                          <p className="text-xs text-gray-500 mt-1">
                            → {getCatalogName(file.classified_catalog_id)}
                          </p>
                          {file.error_message && (
                            <p className="text-xs text-red-500 mt-1">{file.error_message}</p>
                          )}
                          {file.metadata && Object.keys(file.metadata).length > 0 && (
                            <div className="mt-2 p-2 bg-gray-50 rounded text-xs">
                              <p className="font-medium text-gray-600 mb-1">Extracted Metadata:</p>
                              {Object.entries(file.metadata).map(([key, value]) => (
                                <p key={key} className="text-gray-500 truncate" title={String(value)}>
                                  <span className="font-medium">{key}:</span> {String(value).substring(0, 100)}
                                  {String(value).length > 100 && '...'}
                                </p>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </>
          )}

          {/* No results */}
          {!lastExecutionResult && (
            <div className="text-center py-12">
              <FileText className="w-12 h-12 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500">No execution results available</p>
              <p className="text-sm text-gray-400 mt-1">Run the pipeline to see processed files</p>
            </div>
          )}
        </div>

        {/* Right: Stats */}
        <aside className="w-80 bg-white border-l flex flex-col">
          {/* Execution Stats */}
          <div className="p-4 border-b">
            <h2 className="text-sm font-medium text-gray-500 mb-3">Execution Summary</h2>
            {stats ? (
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-sm">
                  <Clock className="w-4 h-4 text-gray-400" />
                  <span className="text-gray-600">Execution Time:</span>
                  <span className="font-medium ml-auto">{stats.executionTime}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Total Files</span>
                  <span className="font-medium">{stats.totalFiles}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Total Folders</span>
                  <span className="font-medium">{stats.totalFolders}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Successful</span>
                  <span className="font-medium text-green-600">{stats.successful}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Failed</span>
                  <span className="font-medium text-red-600">{stats.failed}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Success Rate</span>
                  <span className="font-medium text-green-600">{stats.successRate}</span>
                </div>
              </div>
            ) : (
              <p className="text-sm text-gray-400">No stats available</p>
            )}
          </div>

          {/* Classification Summary */}
          {lastExecutionResult && (
            <div className="p-4 border-b">
              <h2 className="text-sm font-medium text-gray-500 mb-3">Classification Summary</h2>
              <div className="space-y-2">
                {(() => {
                  const catalogCounts: Record<string, number> = {};
                  files.forEach((file) => {
                    const name = getCatalogName(file.classified_catalog_id);
                    catalogCounts[name] = (catalogCounts[name] || 0) + 1;
                  });
                  return Object.entries(catalogCounts).map(([name, count]) => (
                    <div key={name} className="flex justify-between text-sm">
                      <span className="text-gray-600 truncate" title={name}>{name}</span>
                      <span className="font-medium">{count}</span>
                    </div>
                  ));
                })()}
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="p-4 mt-auto">
            <Button 
              variant="outline" 
              className="w-full"
              onClick={() => navigate(`/routine/${routine.id}/edit`)}
            >
              Edit Pipeline
            </Button>
          </div>
        </aside>
      </div>
    </div>
  );
}
