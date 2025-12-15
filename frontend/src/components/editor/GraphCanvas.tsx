import { useCallback, useEffect, useMemo } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  type Node as FlowNode,
  type Edge,
  type Connection,
  type OnNodesChange,
  type OnEdgesChange,
  type OnConnect,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { useRoutineStore } from '@/store';
import { nodeTypes } from './nodes';
import type { Node, NodeType, S3ConnectorData, CollectionData } from '@/types';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyNode = FlowNode<any>;

// Convert our nodes to React Flow nodes
function toFlowNodes(nodes: Node[]): AnyNode[] {
  return nodes.map((node) => ({
    id: node.id,
    type: node.type,
    position: node.position,
    data: node.data,
  }));
}

// Convert our connections to React Flow edges
function toFlowEdges(connections: { id: string; from: string; to: string }[]): Edge[] {
  return connections.map((conn) => ({
    id: conn.id,
    source: conn.from,
    target: conn.to,
    type: 'smoothstep',
    animated: true,
    style: { stroke: '#94a3b8', strokeWidth: 2 },
  }));
}

export function GraphCanvas() {
  const {
    currentRoutine,
    selectedNodeId,
    setSelectedNodeId,
    addNode,
    updateNode,
    deleteNode,
    addConnection,
    deleteConnection,
  } = useRoutineStore();

  const routineNodes = useMemo(() => currentRoutine?.nodes || [], [currentRoutine?.nodes]);
  const routineConnections = useMemo(() => currentRoutine?.connections || [], [currentRoutine?.connections]);

  const [nodes, setNodes, onNodesChange] = useNodesState<AnyNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  // Sync nodes when routine changes
  useEffect(() => {
    setNodes(toFlowNodes(routineNodes));
  }, [routineNodes, setNodes]);

  // Sync edges when connections change
  useEffect(() => {
    setEdges(toFlowEdges(routineConnections));
  }, [routineConnections, setEdges]);

  // Sync nodes with React Flow
  const handleNodesChange: OnNodesChange<AnyNode> = useCallback(
    (changes) => {
      onNodesChange(changes);
      
      // Handle position changes
      changes.forEach((change) => {
        if (change.type === 'position' && change.position) {
          updateNode(change.id, { position: change.position });
        }
        if (change.type === 'remove') {
          deleteNode(change.id);
        }
      });
    },
    [onNodesChange, updateNode, deleteNode]
  );

  // Sync edges with React Flow  
  const handleEdgesChange: OnEdgesChange<Edge> = useCallback(
    (changes) => {
      onEdgesChange(changes);
      
      changes.forEach((change) => {
        if (change.type === 'remove') {
          deleteConnection(change.id);
        }
      });
    },
    [onEdgesChange, deleteConnection]
  );

  // Handle new connections
  const handleConnect: OnConnect = useCallback(
    (connection: Connection) => {
      if (connection.source && connection.target) {
        const newEdge: Edge = {
          id: `conn-${Date.now()}`,
          source: connection.source,
          target: connection.target,
          type: 'smoothstep',
          animated: true,
          style: { stroke: '#94a3b8', strokeWidth: 2 },
        };
        setEdges((eds) => addEdge(newEdge, eds));
        addConnection({
          id: newEdge.id,
          from: connection.source,
          to: connection.target,
        });
      }
    },
    [setEdges, addConnection]
  );

  // Handle node selection
  const handleNodeClick = useCallback(
    (_event: React.MouseEvent, node: AnyNode) => {
      setSelectedNodeId(node.id);
    },
    [setSelectedNodeId]
  );

  // Handle canvas click (deselect)
  const handlePaneClick = useCallback(() => {
    setSelectedNodeId(null);
  }, [setSelectedNodeId]);

  // Get default node data
  const getDefaultNodeData = useCallback((type: NodeType): Node['data'] => {
    const count = routineNodes.filter((n) => n.type === type).length + 1;
    
    switch (type) {
      case 's3-connector':
        return {
          type: 's3-connector',
          name: `S3 Connector ${count}`,
          providerType: 'aws',
          prefix: '',
          syncMode: 'incremental',
          accessKey: '',
          secretKey: '',
          bucket: '',
          region: 'us-east-1',
        } as S3ConnectorData;
      case 'collection':
        return {
          type: 'collection',
          name: `Collection ${count}`,
          collectionName: '',
        } as CollectionData;
    }
  }, [routineNodes]);

  // Handle drop from palette
  const handleDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      
      const type = event.dataTransfer.getData('application/reactflow') as NodeType;
      if (!type) return;

      const reactFlowBounds = event.currentTarget.getBoundingClientRect();
      const position = {
        x: event.clientX - reactFlowBounds.left - 80,
        y: event.clientY - reactFlowBounds.top - 30,
      };

      const newNode: Node = {
        id: `node-${Date.now()}`,
        type,
        position,
        data: getDefaultNodeData(type),
      };

      // Add to store (this will trigger useEffect to update React Flow nodes)
      addNode(newNode);
      setSelectedNodeId(newNode.id);
    },
    [addNode, setSelectedNodeId, getDefaultNodeData]
  );

  const handleDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  return (
    <div className="flex-1 h-full" onDrop={handleDrop} onDragOver={handleDragOver}>
      <ReactFlow
        nodes={nodes.map((n) => ({ ...n, selected: n.id === selectedNodeId }))}
        edges={edges}
        onNodesChange={handleNodesChange}
        onEdgesChange={handleEdgesChange}
        onConnect={handleConnect}
        onNodeClick={handleNodeClick}
        onPaneClick={handlePaneClick}
        nodeTypes={nodeTypes}
        fitView
        snapToGrid
        snapGrid={[20, 20]}
        defaultEdgeOptions={{
          type: 'smoothstep',
          animated: true,
          style: { stroke: '#94a3b8', strokeWidth: 2 },
        }}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={20} size={1} color="#d1d5db" />
        <Controls />
        <MiniMap 
          nodeColor={(node) => {
            if (node.type === 's3-connector') return '#fed7aa';
            if (node.type === 'collection') return '#99f6e4';
            return '#e5e7eb';
          }}
          maskColor="rgba(0, 0, 0, 0.1)"
        />
      </ReactFlow>
    </div>
  );
}
