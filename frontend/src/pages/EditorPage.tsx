import { useEffect, useRef, useCallback, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Save, Play, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NodePalette } from '@/components/editor/NodePalette';
import { GraphCanvas } from '@/components/editor/GraphCanvas';
import { ConfigPanel } from '@/components/editor/ConfigPanel';
import { useRoutineStore } from '@/store';
import { buildIngestionRequest, runIngestionPipeline } from '@/api';

export function EditorPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const {
    routines,
    currentRoutine,
    selectedNodeId,
    setCurrentRoutine,
    setSelectedNodeId,
    deleteNode,
    updateRoutine,
    setExecutionState,
    setLastExecutionResult,
  } = useRoutineStore();
  
  // Use ref to track if we've loaded the routine
  const hasLoaded = useRef(false);
  
  // Loading state for pipeline execution
  const [isExecuting, setIsExecuting] = useState(false);
  const [executionError, setExecutionError] = useState<string | null>(null);

  // Keyboard shortcuts handler
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    // Don't trigger shortcuts when typing in input/textarea
    const target = e.target as HTMLElement;
    if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') {
      return;
    }

    // Delete/Backspace - delete selected node
    if ((e.key === 'Delete' || e.key === 'Backspace') && selectedNodeId) {
      e.preventDefault();
      deleteNode(selectedNodeId);
    }

    // Escape - deselect node
    if (e.key === 'Escape') {
      e.preventDefault();
      setSelectedNodeId(null);
    }
  }, [selectedNodeId, deleteNode, setSelectedNodeId]);

  // Set up keyboard event listener
  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  // Load routine when page opens (only once)
  useEffect(() => {
    if (hasLoaded.current) return;
    
    const routine = routines.find((r) => r.id === id);
    if (routine) {
      setCurrentRoutine(routine);
      hasLoaded.current = true;
    } else {
      navigate('/');
    }
  }, [id, routines, navigate, setCurrentRoutine]);

  const handleSave = () => {
    if (!currentRoutine) return;
    
    updateRoutine(currentRoutine.id, {
      nodes: currentRoutine.nodes,
      connections: currentRoutine.connections,
    });
    
    // Show some feedback
    alert('Routine saved!');
  };

  const handleActivate = async () => {
    if (!currentRoutine || isExecuting) return;
    
    // Validate: need at least S3 and 1 Collection
    const hasS3 = currentRoutine.nodes.some((n) => n.type === 's3-connector');
    const hasCollection = currentRoutine.nodes.some((n) => n.type === 'collection');
    
    if (!hasS3 || !hasCollection) {
      alert('Please add at least: 1 S3 Connector and 1 Collection');
      return;
    }
    
    // Clear previous errors
    setExecutionError(null);
    setIsExecuting(true);
    setExecutionState({ status: 'running', startTime: new Date().toISOString() });
    
    try {
      // Build the ingestion request from routine configuration
      const request = buildIngestionRequest(currentRoutine);
      console.log('Ingestion request:', request);
      
      // Run the pipeline
      const response = await runIngestionPipeline(request);
      console.log('Ingestion response:', response);
      
      // Store results
      setLastExecutionResult(response);
      setExecutionState({ 
        status: response.success ? 'completed' : 'failed',
        startTime: new Date().toISOString(),
        endTime: new Date().toISOString(),
        response,
      });
      
      // Update routine status
      updateRoutine(currentRoutine.id, {
        status: 'active',
        nodes: currentRoutine.nodes,
        connections: currentRoutine.connections,
      });
      
      // Navigate to viewer
      navigate(`/routine/${currentRoutine.id}/view`);
      
    } catch (error) {
      console.error('Pipeline execution failed:', error);
      const errorMessage = error instanceof Error ? error.message : 'Pipeline execution failed';
      setExecutionError(errorMessage);
      setExecutionState({ 
        status: 'failed',
        error: errorMessage,
      });
    } finally {
      setIsExecuting(false);
    }
  };

  const handleNameChange = (name: string) => {
    if (!currentRoutine) return;
    setCurrentRoutine({ ...currentRoutine, name });
  };

  const handleBack = () => {
    // Save before leaving
    if (currentRoutine) {
      updateRoutine(currentRoutine.id, {
        nodes: currentRoutine.nodes,
        connections: currentRoutine.connections,
      });
    }
    navigate('/');
  };

  if (!currentRoutine) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-gray-500">Loading...</p>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col">
      {/* Top Bar */}
      <header className="bg-white border-b px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={handleBack} disabled={isExecuting}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <Input
            value={currentRoutine.name}
            onChange={(e) => handleNameChange(e.target.value)}
            className="w-64 font-medium"
            disabled={isExecuting}
          />
          <span className="text-sm text-gray-500">
            Project: {currentRoutine.projectName}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={handleSave} disabled={isExecuting}>
            <Save className="h-4 w-4 mr-2" />
            Save
          </Button>
          <Button onClick={handleActivate} disabled={isExecuting}>
            {isExecuting ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Running...
              </>
            ) : (
              <>
                <Play className="h-4 w-4 mr-2" />
                Run Pipeline
              </>
            )}
          </Button>
        </div>
      </header>

      {/* Execution Status Banner */}
      {isExecuting && (
        <div className="bg-blue-50 border-b border-blue-200 px-4 py-3">
          <div className="flex items-center gap-3">
            <Loader2 className="h-5 w-5 text-blue-600 animate-spin" />
            <div>
              <p className="text-sm font-medium text-blue-800">
                Running ingestion pipeline...
              </p>
              <p className="text-xs text-blue-600">
                This may take several minutes depending on the number of files.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Error Banner */}
      {executionError && !isExecuting && (
        <div className="bg-red-50 border-b border-red-200 px-4 py-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-red-800">
                Pipeline execution failed
              </p>
              <p className="text-xs text-red-600">{executionError}</p>
            </div>
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={() => setExecutionError(null)}
              className="text-red-600 hover:text-red-800"
            >
              Dismiss
            </Button>
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        <NodePalette />
        <GraphCanvas />
        {selectedNodeId && <ConfigPanel />}
      </div>
    </div>
  );
}
