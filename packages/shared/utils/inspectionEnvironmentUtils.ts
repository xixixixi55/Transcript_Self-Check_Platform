import type { InspectionEnvironmentSnapshot, ProcessStep } from '../types'

function text(value: unknown): string {
  return value == null ? '' : String(value).trim()
}

export function buildInspectionEnvironmentStep(
  hardwareDevice: string,
  snapshot: InspectionEnvironmentSnapshot,
): string {
  const hardware = text(hardwareDevice) || '检查硬件设备待确认'
  const operatingSystem = snapshot.operating_system.status === 'detected'
    && text(snapshot.operating_system.display_name)
    ? text(snapshot.operating_system.display_name)
    : '操作系统信息待确认'
  const operatingSystemStartup = snapshot.operating_system.status === 'detected'
    && text(snapshot.operating_system.display_name)
    ? `${operatingSystem}操作系统启动正常`
    : `${operatingSystem}启动正常`
  const security = snapshot.security_software

  if (security.status === 'detected' || security.status === 'version_unknown') {
    const name = text(security.name) || '火绒安全软件'
    const version = security.status === 'detected' && text(security.version)
      ? `版本号为${text(security.version)}` : '版本号待确认'
    return `启动${hardware}，${operatingSystemStartup}，使用${name}（${version}）对${hardware}进行杀毒，未发现病毒，完毕后退出${name}。`
  }

  return `启动${hardware}，${operatingSystemStartup}，安全软件待确认（版本号待确认），对${hardware}进行杀毒的结果待确认。`
}

export function projectInspectionEnvironmentStep(
  steps: ProcessStep[],
  hardwareDevice: string,
  snapshot: InspectionEnvironmentSnapshot,
): ProcessStep[] {
  return steps.map(step => step.step_number === 3
    ? { ...step, content: buildInspectionEnvironmentStep(hardwareDevice, snapshot) }
    : step)
}
