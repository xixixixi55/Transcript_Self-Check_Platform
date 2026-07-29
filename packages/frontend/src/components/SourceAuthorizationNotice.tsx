import React from 'react'
import { Alert } from 'antd'

export function SourceAuthorizationNotice() {
  return (
    <Alert
      type="info"
      showIcon
      message="来源目录授权说明"
      description={(
        <ul>
          <li>所选目录必须位于后端授权的输入根目录内。</li>
          <li>授权配置必须在后端启动前生效。</li>
          <li>修改授权配置后需要重启后端。</li>
        </ul>
      )}
    />
  )
}
