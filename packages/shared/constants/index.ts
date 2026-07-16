// Layer 1: SharedConstants — 前后端共享的常量

import { RecordType } from '../types'

/** 文书类型中文标签映射 */
export const RECORD_TYPE_LABELS: Record<RecordType, string> = {
  [RecordType.ELECTRONIC_INSPECTION]: '电子数据检查笔录',
  [RecordType.FORENSIC_REPORT]: '专业化勘查报告',
  [RecordType.DIGITAL_FORENSIC]: '电子数据鉴定文书',
  [RecordType.SCENE_TRIPLE_RECORD]: '传统现场三录',
  [RecordType.SCENE_INSPECTION]: '传统现场检查笔录',
  [RecordType.FORENSIC_MEDICAL]: '法医鉴定文书',
}

/** API 基础路径 */
export const API_PREFIX = '/api/v1'

/** API 端点 */
export const API_ENDPOINTS = {
  PARSE_REPORT: `${API_PREFIX}/reports/parse`,
  EXPORT_RECORD: `${API_PREFIX}/records/export`,
  DEVICES: `${API_PREFIX}/devices`,
  UPLOAD_PHOTO: `${API_PREFIX}/photos/upload`,
  PHOTO_FILE: (id: string) => `${API_PREFIX}/photos/${id}`,
}

/** 文件上传限制（字节） */
export const MAX_UPLOAD_SIZE = 50 * 1024 * 1024 // 50MB

/** 支持的输入文件格式 */
export const SUPPORTED_INPUT_FORMATS = ['.html', '.htm']

/** 输出文件格式 */
export const OUTPUT_FORMAT = '.docx'

/** 数据摘要默认值：仅用于缺失或空白输入，数据分类列表不直接映射到该字段 */
export const DEFAULT_DATA_SUMMARY = '即时通讯、手机信息'

/** 支持的图片上传格式 */
export const SUPPORTED_IMAGE_FORMATS = ['.jpg', '.jpeg', '.png']

/** 图片上传大小限制 */
export const MAX_IMAGE_SIZE = 10 * 1024 * 1024 // 10MB

/** 支持的压缩包上传格式 */
export const SUPPORTED_ARCHIVE_FORMATS = ['.rar', '.zip']

/** 压缩包上传大小限制 */
export const ARCHIVE_MAX_SIZE = 500 * 1024 * 1024 // 500MB

// ─── 笔录固定文本 ───

/** 检查方法（固定，不修改） */
export const INSPECTION_METHOD_TEXT =
  '采用 GA/T 1069-2021《法庭科学电子物证手机检验技术规范》进行检查。'

/** 检查要求（固定） */
export const INSPECTION_REQUIREMENT_TEXT = '上述检材内电子数据的提取、固定和恢复'

// ─── 检查过程模板 ───

/** 检查过程第1步模板 */
export const PROCESS_STEP_1 = (model: string, imei1: string, imei2: string, evidenceNumber: string) =>
  `将${model}（IMEI1：${imei1}；IMEI2：${imei2}）编号为${evidenceNumber}。`

/** 检查过程第2步模板 */
export const PROCESS_STEP_2 = (evidenceNumber: string) =>
  `对检材${evidenceNumber}进行拍照。`

/** 检查过程第3步（固定） */
export const PROCESS_STEP_3 =
  '启动美亚FL-901手机取证塔，Windows 10 64位企业版操作系统启动正常，使用火绒安全软件（版本号为6.0.6.1）对取证塔进行杀毒，未发现病毒，完毕后退出火绒安全软件。'

/** 检查过程第4步模板 */
export const PROCESS_STEP_4 = (softwareVersion: string, evidenceNumber: string) =>
  `启动美亚手机大师-并行版V5软件（版本号为${softwareVersion}）使用美亚手机大师-并行版V5软件对检材${evidenceNumber}进行检查。`

/** 检查结果模板 */
export const INSPECTION_RESULT_TEMPLATE = (
  evidenceNumber: string,
  softwareName: string,
  softwareVersion: string,
  dataSummary: string,
  rarFilename: string,
  md5Hash: string,
  fileSize: string,
) =>
  `经对编号为${evidenceNumber}号检材使用${softwareName}（版本号为${softwareVersion}）进行检查，检出${dataSummary}等电子数据。` +
  `将检出结果生成为"${rarFilename}"文件，文件MD5哈希值为"${md5Hash}"，文件大小为"${fileSize}"字节。`

// ─── 默认值 ───

/** 默认检查过程步骤 */
export const DEFAULT_PROCESS_STEPS = 4

/** 默认检查人员数量 */
export const DEFAULT_INSPECTOR_COUNT = 2

/** 附件数量 */
export const ATTACHMENT_COUNT = 3
