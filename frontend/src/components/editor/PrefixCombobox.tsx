import { useCallback } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import type { S3ConnectorData } from '@/types';

interface PrefixInputProps {
  value: string;
  onChange: (value: string) => void;
  s3Data: S3ConnectorData;
  disabled?: boolean;
  onBrowseClick?: () => void;
}

export function PrefixCombobox({
  value,
  onChange,
  s3Data,
  disabled = false,
  onBrowseClick,
}: PrefixInputProps) {
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

  const canBrowse = hasCredentials() && !disabled;

  return (
    <div className="flex gap-2">
      <Input
        value={value}
        readOnly
        disabled={disabled}
        placeholder="Click Browse to select a folder path"
        className="flex-1 cursor-pointer bg-gray-50"
        onClick={canBrowse && onBrowseClick ? onBrowseClick : undefined}
      />
      {onBrowseClick && (
        <Button
          type="button"
          variant="outline"
          onClick={onBrowseClick}
          disabled={!canBrowse || disabled}
        >
          Browse...
        </Button>
      )}
    </div>
  );
}

