import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Pencil, Trash2, Copy } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Input } from '@/components/ui/input';
import { CreateRoutineModal } from '@/components/CreateRoutineModal';
import { useRoutineStore } from '@/store';
import type { Routine } from '@/types';

export function RoutinesPage() {
  const navigate = useNavigate();
  const { routines, deleteRoutine, addRoutine } = useRoutineStore();
  const [search, setSearch] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);

  const filteredRoutines = routines.filter((r) =>
    r.name.toLowerCase().includes(search.toLowerCase()) ||
    r.projectName.toLowerCase().includes(search.toLowerCase())
  );

  const handleRowClick = (routine: Routine) => {
    if (routine.status === 'draft') {
      navigate(`/routine/${routine.id}/edit`);
    } else {
      navigate(`/routine/${routine.id}/view`);
    }
  };

  const handleEdit = (e: React.MouseEvent, routine: Routine) => {
    e.stopPropagation();
    navigate(`/routine/${routine.id}/edit`);
  };

  const handleDuplicate = (e: React.MouseEvent, routine: Routine) => {
    e.stopPropagation();
    const duplicated: Routine = {
      ...routine,
      id: `routine-${Date.now()}`,
      name: `${routine.name} (copy)`,
      status: 'draft',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    addRoutine(duplicated);
  };

  const handleDelete = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (confirm('Are you sure you want to delete this routine?')) {
      deleteRoutine(id);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('vi-VN', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getS3Source = (routine: Routine) => {
    const s3Node = routine.nodes.find((n) => n.data.type === 's3-connector');
    if (s3Node && s3Node.data.type === 's3-connector') {
      return s3Node.data.bucket || '-';
    }
    return '-';
  };

  const getCollectionsCount = (routine: Routine) => {
    return routine.nodes.filter((n) => n.data.type === 'collection').length;
  };

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="bg-white border-b px-6 py-4">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-2xl font-semibold text-gray-900">Data Routines</h1>
          <p className="text-sm text-gray-500 mt-1">
            Manage your data classification routines
          </p>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-6 py-6">
        {/* Toolbar */}
        <div className="flex items-center justify-between mb-6">
          <Input
            placeholder="Search routines..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="max-w-xs"
          />
          <Button onClick={() => setShowCreateModal(true)}>
            <Plus className="h-4 w-4 mr-2" />
            New Routine
          </Button>
        </div>

        {/* Table */}
        <div className="bg-white rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Project</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>S3 Source</TableHead>
                <TableHead>Collections</TableHead>
                <TableHead>Last Modified</TableHead>
                <TableHead className="w-[100px]">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredRoutines.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-gray-500 py-8">
                    {routines.length === 0
                      ? 'No routines yet. Create your first routine to get started.'
                      : 'No routines match your search.'}
                  </TableCell>
                </TableRow>
              ) : (
                filteredRoutines.map((routine) => (
                  <TableRow
                    key={routine.id}
                    className="cursor-pointer"
                    onClick={() => handleRowClick(routine)}
                  >
                    <TableCell className="font-medium">{routine.name}</TableCell>
                    <TableCell>{routine.projectName}</TableCell>
                    <TableCell>
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                          routine.status === 'active'
                            ? 'bg-green-100 text-green-800'
                            : 'bg-gray-100 text-gray-800'
                        }`}
                      >
                        {routine.status === 'active' ? 'Active' : 'Draft'}
                      </span>
                    </TableCell>
                    <TableCell className="text-gray-500">{getS3Source(routine)}</TableCell>
                    <TableCell>{getCollectionsCount(routine)}</TableCell>
                    <TableCell className="text-gray-500">
                      {formatDate(routine.updatedAt)}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        {routine.status === 'draft' && (
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={(e) => handleEdit(e, routine)}
                            title="Edit"
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={(e) => handleDuplicate(e, routine)}
                          title="Duplicate"
                        >
                          <Copy className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={(e) => handleDelete(e, routine.id)}
                          title="Delete"
                        >
                          <Trash2 className="h-4 w-4 text-red-500" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </main>

      {/* Create Modal */}
      <CreateRoutineModal
        open={showCreateModal}
        onOpenChange={setShowCreateModal}
      />
    </div>
  );
}



