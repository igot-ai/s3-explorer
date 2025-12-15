import { Cloud, FolderOpen } from 'lucide-react';
import type { NodeType } from '@/types';

const nodeTypes: { type: NodeType; label: string; icon: React.ElementType; color: string }[] = [
  { type: 's3-connector', label: 'S3 Connector', icon: Cloud, color: 'bg-orange-500' },
  { type: 'collection', label: 'Collection', icon: FolderOpen, color: 'bg-teal-500' },
];

export function NodePalette() {
  const handleDragStart = (e: React.DragEvent, type: NodeType) => {
    e.dataTransfer.setData('application/reactflow', type);
    e.dataTransfer.effectAllowed = 'move';
  };

  return (
    <aside className="w-48 bg-white border-r p-4">
      <h3 className="text-sm font-medium text-gray-500 mb-3">Components</h3>
      <div className="space-y-2">
        {nodeTypes.map(({ type, label, icon: Icon, color }) => (
          <div
            key={type}
            draggable
            onDragStart={(e) => handleDragStart(e, type)}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-white text-sm font-medium cursor-grab active:cursor-grabbing ${color} hover:opacity-90 transition-opacity`}
          >
            <Icon className="h-4 w-4" />
            {label}
          </div>
        ))}
      </div>

      <div className="mt-6 pt-4 border-t">
        <h4 className="text-xs font-medium text-gray-400 mb-2">Instructions</h4>
        <ul className="text-xs text-gray-500 space-y-1">
          <li>• Drag components onto canvas</li>
          <li>• Click nodes to configure</li>
          <li>• Drag from output to connect</li>
          <li>• Each node has 1 output</li>
        </ul>
      </div>
    </aside>
  );
}

