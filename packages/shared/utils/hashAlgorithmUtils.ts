import type { HashAlgorithm } from '../types'

const HASH_LABELS: Record<HashAlgorithm, string> = {
  md5: 'MD5',
  sha1: 'SHA-1',
  sha256: 'SHA-256',
}

export function normalizeHashAlgorithm(value: unknown): HashAlgorithm {
  const normalized = typeof value === 'string' ? value.toLowerCase().replace('-', '') : ''
  return normalized === 'sha1' || normalized === 'sha256' ? normalized : 'md5'
}

export function hashAlgorithmLabel(value: unknown): string {
  return HASH_LABELS[normalizeHashAlgorithm(value)]
}

export function hashFieldTitle(value: unknown): string {
  return `文件${hashAlgorithmLabel(value)}哈希值`
}

export function hashExtractionMethod(hardwareDevice: string, value: unknown): string {
  return `使用${hardwareDevice.trim() || '取证设备'}对检材进行检查，将检出数据生成报告，然后对报告压缩并计算${hashAlgorithmLabel(value)}值`
}
