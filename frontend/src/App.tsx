import { Routes, Route, Navigate } from 'react-router-dom';
import { RoutinesPage } from './pages/RoutinesPage';
import { EditorPage } from './pages/EditorPage';
import { ViewerPage } from './pages/ViewerPage';

export default function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <Routes>
        <Route path="/" element={<RoutinesPage />} />
        <Route path="/routine/:id/edit" element={<EditorPage />} />
        <Route path="/routine/:id/view" element={<ViewerPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}



