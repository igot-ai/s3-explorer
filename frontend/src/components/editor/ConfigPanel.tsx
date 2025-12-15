import { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useRoutineStore } from '@/store';
import { fetchCollections } from '@/api';
import type { Node, S3ConnectorData, CollectionData, StorageProviderType } from '@/types';
import { AWS_REGIONS, WASABI_REGIONS, DIGITALOCEAN_REGIONS, HETZNER_REGIONS } from '@/types';

// Collection type from API
interface CatalogCollection {
  id: string;
  name: string;
  description?: string;
  project_id: string;
}

// Provider configuration metadata
const PROVIDER_OPTIONS: { value: StorageProviderType; label: string }[] = [
  { value: 'aws', label: 'Amazon S3' },
  { value: 'cloudflare', label: 'Cloudflare R2' },
  { value: 'backblaze', label: 'Backblaze B2' },
  { value: 'wasabi', label: 'Wasabi' },
  { value: 'gcs', label: 'Google Cloud Storage' },
  { value: 'digitalocean', label: 'DigitalOcean Spaces' },
  { value: 'hetzner', label: 'Hetzner Storage' },
];

// ============ S3ConnectorFields Component ============

interface S3ConnectorFieldsProps {
  data: S3ConnectorData;
  updateNodeData: (updates: Partial<S3ConnectorData>) => void;
}

function S3ConnectorFields({ data, updateNodeData }: S3ConnectorFieldsProps) {
  const providerType = data.providerType || 'aws';

  // Get region options based on provider
  const getRegionOptions = () => {
    switch (providerType) {
      case 'aws':
        return AWS_REGIONS;
      case 'wasabi':
        return WASABI_REGIONS;
      case 'digitalocean':
        return DIGITALOCEAN_REGIONS;
      case 'hetzner':
        return HETZNER_REGIONS;
      default:
        return [];
    }
  };

  const regionOptions = getRegionOptions();
  const showRegionField = ['aws', 'wasabi', 'digitalocean', 'hetzner'].includes(providerType);

  return (
    <>
      {/* Provider Type Selection */}
      <div className="space-y-2">
        <label className="text-sm font-medium">Storage Provider</label>
        <Select
          value={providerType}
          onValueChange={(value: StorageProviderType) => updateNodeData({ providerType: value })}
        >
          <SelectTrigger>
            <SelectValue placeholder="Select provider..." />
          </SelectTrigger>
          <SelectContent>
            {PROVIDER_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* AWS / Wasabi / DigitalOcean / Hetzner Fields */}
      {['aws', 'wasabi', 'digitalocean', 'hetzner'].includes(providerType) && (
        <>
          <div className="space-y-2">
            <label className="text-sm font-medium">Access Key</label>
            <Input
              value={data.accessKey || ''}
              onChange={(e) => updateNodeData({ accessKey: e.target.value })}
              placeholder="Access Key ID"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Secret Key</label>
            <Input
              type="password"
              value={data.secretKey || ''}
              onChange={(e) => updateNodeData({ secretKey: e.target.value })}
              placeholder="Secret Access Key"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Bucket Name</label>
            <Input
              value={data.bucket || ''}
              onChange={(e) => updateNodeData({ bucket: e.target.value })}
              placeholder="my-bucket"
            />
          </div>
          {showRegionField && (
            <div className="space-y-2">
              <label className="text-sm font-medium">Region</label>
              <Select
                value={data.region || ''}
                onValueChange={(value) => updateNodeData({ region: value })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select region..." />
                </SelectTrigger>
                <SelectContent>
                  {regionOptions.map((region) => (
                    <SelectItem key={region} value={region}>
                      {region}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
        </>
      )}

      {/* Cloudflare R2 Fields */}
      {providerType === 'cloudflare' && (
        <>
          <div className="space-y-2">
            <label className="text-sm font-medium">Account ID</label>
            <Input
              value={data.accountId || ''}
              onChange={(e) => updateNodeData({ accountId: e.target.value })}
              placeholder="Cloudflare Account ID"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Access Key</label>
            <Input
              value={data.accessKey || ''}
              onChange={(e) => updateNodeData({ accessKey: e.target.value })}
              placeholder="R2 Access Key ID"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Secret Key</label>
            <Input
              type="password"
              value={data.secretKey || ''}
              onChange={(e) => updateNodeData({ secretKey: e.target.value })}
              placeholder="R2 Secret Access Key"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Bucket Name</label>
            <Input
              value={data.bucket || ''}
              onChange={(e) => updateNodeData({ bucket: e.target.value })}
              placeholder="my-r2-bucket"
            />
          </div>
        </>
      )}

      {/* Backblaze B2 Fields */}
      {providerType === 'backblaze' && (
        <>
          <div className="space-y-2">
            <label className="text-sm font-medium">Application Key ID</label>
            <Input
              value={data.applicationKeyId || ''}
              onChange={(e) => updateNodeData({ applicationKeyId: e.target.value })}
              placeholder="Application Key ID"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Application Key</label>
            <Input
              type="password"
              value={data.applicationKey || ''}
              onChange={(e) => updateNodeData({ applicationKey: e.target.value })}
              placeholder="Application Key"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Bucket Name</label>
            <Input
              value={data.bucketName || ''}
              onChange={(e) => updateNodeData({ bucketName: e.target.value })}
              placeholder="my-b2-bucket"
            />
          </div>
        </>
      )}

      {/* Google Cloud Storage Fields */}
      {providerType === 'gcs' && (
        <>
          <div className="space-y-2">
            <label className="text-sm font-medium">Project ID</label>
            <Input
              value={data.projectId || ''}
              onChange={(e) => updateNodeData({ projectId: e.target.value })}
              placeholder="my-gcp-project"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Bucket Name</label>
            <Input
              value={data.bucketName || ''}
              onChange={(e) => updateNodeData({ bucketName: e.target.value })}
              placeholder="my-gcs-bucket"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Service Account JSON</label>
            <textarea
              value={data.credentialsJson || ''}
              onChange={(e) => updateNodeData({ credentialsJson: e.target.value })}
              placeholder='{"type": "service_account", ...}'
              className="w-full h-32 px-3 py-2 text-sm border border-gray-300 rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
            />
            <p className="text-xs text-gray-500">
              Paste the full JSON content of your service account key file
            </p>
          </div>
        </>
      )}

      {/* Common Fields: Prefix and Sync Mode */}
      <div className="space-y-2">
        <label className="text-sm font-medium">Prefix / Path</label>
        <Input
          value={data.prefix || ''}
          onChange={(e) => updateNodeData({ prefix: e.target.value })}
          placeholder="data/incoming/"
        />
        <p className="text-xs text-gray-500">
          Optional path prefix to filter files
        </p>
      </div>
      <div className="space-y-2">
        <label className="text-sm font-medium">Sync Mode</label>
        <Select
          value={data.syncMode || 'incremental'}
          onValueChange={(value: 'incremental' | 'full' | 'manual') => updateNodeData({ syncMode: value })}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="incremental">Incremental</SelectItem>
            <SelectItem value="full">Full Sync</SelectItem>
            <SelectItem value="manual">Manual</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </>
  );
}

// ============ Main ConfigPanel Component ============

export function ConfigPanel() {
  const { currentRoutine, selectedNodeId, setSelectedNodeId, updateNode } = useRoutineStore();
  const [collections, setCollections] = useState<CatalogCollection[]>([]);
  const [loadingCollections, setLoadingCollections] = useState(false);

  const node = currentRoutine?.nodes.find((n) => n.id === selectedNodeId);

  useEffect(() => {
    if (currentRoutine?.projectId) {
      setLoadingCollections(true);
      fetchCollections(currentRoutine.projectId)
        .then(setCollections)
        .catch((err) => {
          console.error('Failed to fetch collections:', err);
          setCollections([]);
        })
        .finally(() => setLoadingCollections(false));
    }
  }, [currentRoutine?.projectId]);

  if (!node) return null;

  const updateNodeData = (updates: Partial<Node['data']>) => {
    updateNode(node.id, {
      data: { ...node.data, ...updates } as Node['data'],
    });
  };

  // Get other collection nodes that can be used as metadata source
  const getOtherCollectionNodes = () => {
    if (!currentRoutine || node.data.type !== 'collection') return [];
    
    return currentRoutine.nodes.filter(
      (n) => n.data.type === 'collection' && n.id !== node.id
    );
  };

  // Get catalog IDs already used by OTHER collection nodes
  const getUsedCatalogIds = (): Set<string> => {
    if (!currentRoutine) return new Set();
    
    const usedIds = new Set<string>();
    currentRoutine.nodes.forEach((n) => {
      if (n.data.type === 'collection' && n.id !== node.id) {
        const catalogId = (n.data as CollectionData).catalogId;
        if (catalogId) {
          usedIds.add(catalogId);
        }
      }
    });
    return usedIds;
  };

  const usedCatalogIds = getUsedCatalogIds();
  
  // Filter available collections (exclude already used ones, keep current selection)
  const currentCatalogId = node.data.type === 'collection' 
    ? (node.data as CollectionData).catalogId 
    : '';
  
  const availableCollections = collections.filter(
    (col) => !usedCatalogIds.has(col.id) || col.id === currentCatalogId
  );

  // Handle collection selection - store both ID and name
  const handleCollectionSelect = (catalogId: string) => {
    const collection = collections.find((c) => c.id === catalogId);
    if (collection) {
      updateNodeData({
        catalogId: collection.id,
        collectionName: collection.name,
        name: collection.name, // Update node name to match collection
      });
    }
  };

  return (
    <aside className="w-80 bg-white border-l flex flex-col">
      <div className="p-4 border-b flex items-center justify-between">
        <h2 className="font-semibold">Configure Node</h2>
        <Button variant="ghost" size="icon" onClick={() => setSelectedNodeId(null)}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Common: Name */}
        <div className="space-y-2">
          <label className="text-sm font-medium">Name</label>
          <Input
            value={node.data.name}
            onChange={(e) => updateNodeData({ name: e.target.value })}
            placeholder="Node name"
          />
        </div>

        {/* S3 Connector fields */}
        {node.data.type === 's3-connector' && (
          <S3ConnectorFields 
            data={node.data as S3ConnectorData} 
            updateNodeData={updateNodeData} 
          />
        )}

        {/* Collection fields */}
        {node.data.type === 'collection' && (
          <>
            <div className="space-y-2">
              <label className="text-sm font-medium">Collection (Catalog)</label>
              <Select
                value={(node.data as CollectionData).catalogId || ''}
                onValueChange={handleCollectionSelect}
              >
                <SelectTrigger>
                  <SelectValue placeholder={loadingCollections ? "Loading..." : "Select collection..."} />
                </SelectTrigger>
                <SelectContent>
                  {availableCollections.map((col) => (
                    <SelectItem key={col.id} value={col.id}>
                      {col.name}
                    </SelectItem>
                  ))}
                  {availableCollections.length === 0 && !loadingCollections && (
                    <div className="px-2 py-1.5 text-sm text-gray-500">
                      No available collections
                    </div>
                  )}
                </SelectContent>
              </Select>
              <p className="text-xs text-gray-500">
                Select the target collection from your project
              </p>
            </div>

            {/* AI Classification Instructions */}
            <div className="space-y-2">
              <label className="text-sm font-medium">Classification Instructions</label>
              <textarea
                value={(node.data as CollectionData).instruction || (node.data as CollectionData & { information?: string }).information || ''}
                onChange={(e) => updateNodeData({ instruction: e.target.value })}
                placeholder="Mô tả loại tài liệu nào thuộc collection này...&#10;&#10;Ví dụ: Chứa các tài liệu hợp đồng, thỏa thuận pháp lý giữa các bên."
                className="w-full h-24 px-3 py-2 text-sm border border-gray-300 rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="text-xs text-gray-500">
                Hướng dẫn AI nhận biết tài liệu thuộc collection này
              </p>
            </div>

            {/* Fetch All Metadata Toggle */}
            <div className="flex items-center justify-between">
              <div>
                <label className="text-sm font-medium">Fetch All Metadata</label>
                <p className="text-xs text-gray-500">
                  Aggregate metadata từ tất cả collections
                </p>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={(node.data as CollectionData).fetchAllMetadata || false}
                onClick={() => updateNodeData({ 
                  fetchAllMetadata: !(node.data as CollectionData).fetchAllMetadata 
                })}
                className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
                  (node.data as CollectionData).fetchAllMetadata 
                    ? 'bg-blue-600' 
                    : 'bg-gray-200'
                }`}
              >
                <span
                  className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                    (node.data as CollectionData).fetchAllMetadata 
                      ? 'translate-x-5' 
                      : 'translate-x-0'
                  }`}
                />
              </button>
            </div>

            {/* Metadata Source Collection */}
            <div className="space-y-2">
              <label className="text-sm font-medium">Metadata Source Collection</label>
              <Select
                value={(node.data as CollectionData).metadataSourceCollectionId || 'none'}
                onValueChange={(value) => 
                  updateNodeData({ metadataSourceCollectionId: value === 'none' ? '' : value })
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="None" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">None</SelectItem>
                  {getOtherCollectionNodes().map((collectionNode) => (
                    <SelectItem key={collectionNode.id} value={collectionNode.id}>
                      {collectionNode.data.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-gray-500">
                Fetch context metadata from another collection
              </p>
            </div>
          </>
        )}
      </div>
    </aside>
  );
}
