// Layer 12: FE_Pages — 应用路由定义

import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { PlatformShell } from './components/PlatformShell'
import ElectronicInspectionModulePage from './pages/ElectronicInspectionModulePage'
import DeviceManagePage from './pages/DeviceManagePage'
import InspectorManagePage from './pages/InspectorManagePage'
import TemplateManagePage from './pages/TemplateManagePage'
import HomePage from './pages/HomePage'
import CaseWorkbenchPage from './pages/CaseWorkbenchPage'
import CaseRecordGeneratePage from './pages/CaseRecordGeneratePage'

export function LegacyRedirect({ to }: { to: string }) {
  const location = useLocation()
  return <Navigate to={`${to}${location.search}${location.hash}`} replace />
}

export default function App() {
  return (
    <PlatformShell>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/electronic-inspection" element={<ElectronicInspectionModulePage />} />
        <Route path="/electronic-inspection/workbench" element={<CaseWorkbenchPage />} />
        <Route path="/electronic-inspection/cases/:caseId" element={<CaseRecordGeneratePage />} />
        <Route path="/electronic-inspection/generate" element={<LegacyRedirect to="/electronic-inspection/workbench" />} />
        <Route path="/electronic-inspection/devices" element={<DeviceManagePage />} />
        <Route path="/electronic-inspection/inspectors" element={<InspectorManagePage />} />
        <Route path="/electronic-inspection/templates" element={<TemplateManagePage />} />
        <Route path="/generate" element={<LegacyRedirect to="/electronic-inspection/workbench" />} />
        <Route path="/devices" element={<LegacyRedirect to="/electronic-inspection/devices" />} />
        <Route path="/inspectors" element={<LegacyRedirect to="/electronic-inspection/inspectors" />} />
        <Route path="/templates" element={<LegacyRedirect to="/electronic-inspection/templates" />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </PlatformShell>
  )
}
