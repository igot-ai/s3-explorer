import { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import { Cloud } from 'lucide-react';
import type { S3ConnectorData } from '@/types';

interface S3ConnectorNodeProps {
  data: S3ConnectorData;
  selected?: boolean;
}

function S3ConnectorNodeComponent({ data, selected }: S3ConnectorNodeProps) {
  return (
    <>
      <Handle
        type="target"
        position={Position.Left}
        className="!w-3 !h-3 !bg-white !border-2 !border-gray-300"
      />
      <div
        className={`w-40 rounded-xl border-2 border-orange-500 bg-orange-100 shadow-sm transition-shadow ${
          selected ? 'ring-2 ring-orange-400 shadow-md' : ''
        }`}
      >
        <div className="p-3">
          <div className="flex items-center gap-2">
            <Cloud className="w-4 h-4 text-orange-600" />
            <span className="text-sm font-medium truncate">
              {data.name || 'S3 Connector'}
            </span>
          </div>
          <p className="text-xs text-gray-500 mt-1">s3 connector</p>
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

export const S3ConnectorNode = memo(S3ConnectorNodeComponent);
