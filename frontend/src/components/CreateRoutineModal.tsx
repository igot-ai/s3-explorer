import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useRoutineStore } from '@/store';
import { fetchProjects } from '@/api';
import type { Routine } from '@/types';

interface CreateRoutineModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CreateRoutineModal({ open, onOpenChange }: CreateRoutineModalProps) {
  const navigate = useNavigate();
  const { projects, setProjects, addRoutine } = useRoutineStore();
  const [name, setName] = useState('');
  const [projectId, setProjectId] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingProjects, setLoadingProjects] = useState(false);

  // Always fetch fresh projects when modal opens
  useEffect(() => {
    if (open) {
      const fetchProjectsAsync = async () => {
        try {
          setLoadingProjects(true);
          const projects = await fetchProjects();
          if (Array.isArray(projects)) {
            setProjects(projects);
          } else {
            console.error('Invalid projects data:', projects);
          }
        } catch (err) {
          console.error('Failed to fetch projects:', err);
        } finally {
          setLoadingProjects(false);
        }
      };
      fetchProjectsAsync();
    }
  }, [open, setProjects]);

  const handleCreate = () => {
    if (!name.trim() || !projectId) return;

    const project = projects.find((p) => p.id === projectId);
    if (!project) return;

    setLoading(true);

    const newRoutine: Routine = {
      id: `routine-${Date.now()}`,
      name: name.trim(),
      projectId,
      projectName: project.name,
      status: 'draft',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      nodes: [],
      connections: [],
    };

    addRoutine(newRoutine);
    setLoading(false);
    onOpenChange(false);
    setName('');
    setProjectId('');
    
    // Navigate to editor
    navigate(`/routine/${newRoutine.id}/edit`);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create New Routine</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Routine Name</label>
            <Input
              placeholder="Enter routine name..."
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Project</label>
            <Select value={projectId} onValueChange={setProjectId}>
              <SelectTrigger>
                <SelectValue placeholder={loadingProjects ? "Loading projects..." : "Select a project..."} />
              </SelectTrigger>
              <SelectContent>
                {projects.map((project) => (
                  <SelectItem key={project.id} value={project.id}>
                    {project.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleCreate}
            disabled={!name.trim() || !projectId || loading}
          >
            {loading ? 'Creating...' : 'Create'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}



