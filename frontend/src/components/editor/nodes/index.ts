import { S3ConnectorNode } from './S3ConnectorNode';
import { CollectionNode } from './CollectionNode';

export const nodeTypes = {
  's3-connector': S3ConnectorNode,
  'collection': CollectionNode,
};

export { S3ConnectorNode, CollectionNode };

