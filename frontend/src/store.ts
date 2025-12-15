import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Routine, Node, Connection, Project, ExecutionState, IngestionResponse } from './types';

interface RoutineStore {
  // Data
  routines: Routine[];
  projects: Project[];
  
  // Current editing routine
  currentRoutine: Routine | null;
  selectedNodeId: string | null;
  
  // Execution state
  executionState: ExecutionState;
  lastExecutionResult: IngestionResponse | null;
  
  // Actions - Routines
  setRoutines: (routines: Routine[]) => void;
  addRoutine: (routine: Routine) => void;
  updateRoutine: (id: string, updates: Partial<Routine>) => void;
  deleteRoutine: (id: string) => void;
  
  // Actions - Current Routine
  setCurrentRoutine: (routine: Routine | null) => void;
  setSelectedNodeId: (nodeId: string | null) => void;
  
  // Actions - Nodes
  addNode: (node: Node) => void;
  updateNode: (nodeId: string, updates: Partial<Node>) => void;
  deleteNode: (nodeId: string) => void;
  
  // Actions - Connections
  addConnection: (connection: Connection) => void;
  deleteConnection: (connectionId: string) => void;
  
  // Actions - Projects
  setProjects: (projects: Project[]) => void;
  
  // Actions - Execution
  setExecutionState: (state: ExecutionState) => void;
  setLastExecutionResult: (result: IngestionResponse | null) => void;
  resetExecution: () => void;
}

export const useRoutineStore = create<RoutineStore>()(
  persist(
    (set, get) => ({
      // Initial state
      routines: [],
      projects: [],
      currentRoutine: null,
      selectedNodeId: null,
      executionState: { status: 'idle' },
      lastExecutionResult: null,
      
      // Routines actions
      setRoutines: (routines) => set({ routines }),
      
      addRoutine: (routine) => set((state) => ({
        routines: [...state.routines, routine],
      })),
      
      updateRoutine: (id, updates) => set((state) => ({
        routines: state.routines.map((r) =>
          r.id === id ? { ...r, ...updates, updatedAt: new Date().toISOString() } : r
        ),
        // Don't update currentRoutine here to avoid infinite loops
        // currentRoutine is managed separately via setCurrentRoutine and node/connection actions
      })),
      
      deleteRoutine: (id) => set((state) => ({
        routines: state.routines.filter((r) => r.id !== id),
        currentRoutine: state.currentRoutine?.id === id ? null : state.currentRoutine,
      })),
      
      // Current routine actions
      setCurrentRoutine: (routine) => set({ currentRoutine: routine, selectedNodeId: null }),
      setSelectedNodeId: (nodeId) => set({ selectedNodeId: nodeId }),
      
      // Node actions
      addNode: (node) => {
        const current = get().currentRoutine;
        if (!current) return;
        
        set({
          currentRoutine: {
            ...current,
            nodes: [...current.nodes, node],
            updatedAt: new Date().toISOString(),
          },
        });
      },
      
      updateNode: (nodeId, updates) => {
        const current = get().currentRoutine;
        if (!current) return;
        
        set({
          currentRoutine: {
            ...current,
            nodes: current.nodes.map((n) =>
              n.id === nodeId ? { ...n, ...updates } : n
            ),
            updatedAt: new Date().toISOString(),
          },
        });
      },
      
      deleteNode: (nodeId) => {
        const current = get().currentRoutine;
        if (!current) return;
        
        set({
          currentRoutine: {
            ...current,
            nodes: current.nodes.filter((n) => n.id !== nodeId),
            connections: current.connections.filter(
              (c) => c.from !== nodeId && c.to !== nodeId
            ),
            updatedAt: new Date().toISOString(),
          },
          selectedNodeId: get().selectedNodeId === nodeId ? null : get().selectedNodeId,
        });
      },
      
      // Connection actions
      addConnection: (connection) => {
        const current = get().currentRoutine;
        if (!current) return;
        
        // Check if source node already has a connection (only 1 output allowed)
        const existingConnection = current.connections.find(
          (c) => c.from === connection.from
        );
        
        if (existingConnection) {
          // Replace existing connection
          set({
            currentRoutine: {
              ...current,
              connections: current.connections.map((c) =>
                c.from === connection.from ? connection : c
              ),
              updatedAt: new Date().toISOString(),
            },
          });
        } else {
          set({
            currentRoutine: {
              ...current,
              connections: [...current.connections, connection],
              updatedAt: new Date().toISOString(),
            },
          });
        }
      },
      
      deleteConnection: (connectionId) => {
        const current = get().currentRoutine;
        if (!current) return;
        
        set({
          currentRoutine: {
            ...current,
            connections: current.connections.filter((c) => c.id !== connectionId),
            updatedAt: new Date().toISOString(),
          },
        });
      },
      
      // Projects actions
      setProjects: (projects) => set({ projects }),
      
      // Execution actions
      setExecutionState: (executionState) => set({ executionState }),
      setLastExecutionResult: (lastExecutionResult) => set({ lastExecutionResult }),
      resetExecution: () => set({ 
        executionState: { status: 'idle' }, 
        lastExecutionResult: null 
      }),
    }),
    {
      name: 'data-routine-storage',
      partialize: (state) => ({
        routines: state.routines,
        projects: state.projects,
        lastExecutionResult: state.lastExecutionResult,
      }),
    }
  )
);

