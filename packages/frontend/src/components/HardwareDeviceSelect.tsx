// Layer 11: FE_Components — managed hardware-device selector shared by record editors.
import { Select } from 'antd'
import type { SelectProps } from 'antd'

export interface HardwareDeviceOption {
  label: string
  value: string
}

interface HardwareDeviceSelectProps extends Omit<SelectProps<string>, 'options'> {
  options: HardwareDeviceOption[]
}

export function HardwareDeviceSelect({ options, loading, ...props }: HardwareDeviceSelectProps) {
  return (
    <Select<string>
      {...props}
      options={options}
      loading={loading}
      showSearch
      optionFilterProp="label"
      notFoundContent={loading ? '正在加载电子设备…' : '暂无电子设备，请先到电子设备管理中添加'}
    />
  )
}
