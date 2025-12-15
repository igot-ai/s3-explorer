import { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import { FolderOpen } from 'lucide-react';
import type { CollectionData } from '@/types';

interface CollectionNodeProps {
  data: CollectionData;
  selected?: boolean;
}

function CollectionNodeComponent({ data, selected }: CollectionNodeProps) {
  return (
    <>
      <Handle
        type="target"
        position={Position.Left}
        className="!w-3 !h-3 !bg-white !border-2 !border-gray-300"
      />
      <div
        className={`w-40 rounded-xl border-2 border-teal-500 bg-teal-100 shadow-sm transition-shadow ${
          selected ? 'ring-2 ring-teal-400 shadow-md' : ''
        }`}
      >
        <div className="p-3">
          <div className="flex items-center gap-2">
            <FolderOpen className="w-4 h-4 text-teal-600" />
            <span className="text-sm font-medium truncate">
              {data.name || 'Collection'}
            </span>
          </div>
          <p className="text-xs text-gray-500 mt-1">collection</p>
        </div>
      </div>
      <Handle
        type="source"
        position={Position.Right}
        className="!w-3 !h-3 !bg-white !border-2 !border-gray-300 hover:!border-blue-500 hover:!bg-blue-50"
      />
    </>
  );
}

export const CollectionNode = memo(CollectionNodeComponent);
