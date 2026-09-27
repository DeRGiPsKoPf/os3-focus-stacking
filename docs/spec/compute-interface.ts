/**
 * Compute interface for focus stacking — TypeScript form of the contract.
 *
 * Normative prose: ./compute-interface.md (this file must stay in sync with it).
 * Interface version: 1.
 *
 * Status: specification only (Step 0). Not compiled yet — it gets copied into
 * the OpenScan3-Client clone in Step 3 (target: app/src/stacking/compute/types.ts)
 * and type-checked there against the client's tsconfig. From then on the client
 * copy is canonical and this file is replaced by a pointer to it.
 *
 * Type declarations plus two constants; no other runtime code.
 */

export const COMPUTE_INTERFACE_VERSION = 1 as const

// ---------------------------------------------------------------------------
// Images and batches
// ---------------------------------------------------------------------------

/**
 * Where a backend obtains the encoded bytes of one photo.
 * - 'url':  the backend fetches it itself (e.g. OS3 photo endpoint with file_only=true).
 * - 'blob': the orchestrator already fetched it (browser backends only).
 */
export type ImageSource =
  | { readonly kind: 'url'; readonly url: string }
  | { readonly kind: 'blob'; readonly blob: Blob }

export interface StackImage {
  /** OS3 photo path relative to the scan directory, e.g. "scan01_004_fs03.jpg". */
  readonly photoPath: string
  /** Focus step as encoded in the file name (fsNN), 0-based. */
  readonly focusStep: number
  readonly source: ImageSource
  /** Encoding of the file. Interface version 1 supports JPEG only (like OS3's own stacking). */
  readonly encoding: 'jpeg'
}

/**
 * All photos of one scan position.
 * Invariant: images.length === stackSize and images[i].focusStep === i.
 */
export interface Batch {
  readonly projectName: string
  readonly scanIndex: number
  /** Position number as encoded in the file name (NNN): OS3's original path index, not capture order. */
  readonly position: number
  readonly images: readonly StackImage[]
}

// ---------------------------------------------------------------------------
// Alignment
// ---------------------------------------------------------------------------

/**
 * 2x3 affine matrix in OpenCV layout (2 rows x 3 columns), JSON-compatible with
 * OS3's calibration file: [[a, b, c], [d, e, f]].
 *
 * Maps OUTPUT (reference-frame) pixel coordinates to SOURCE pixel coordinates:
 *   x_src = a*x + b*y + c
 *   y_src = d*x + e*y + f
 * i.e. applied as cv2.warpAffine(src, M, (w, h), INTER_LINEAR | WARP_INVERSE_MAP,
 * BORDER_CONSTANT with value 0). Full-resolution pixel units, pixel centres at
 * integer coordinates. Values are float32 values carried as JSON numbers.
 * (Same six numbers as a WGSL mat3x2<f32> with columns (a,d), (b,e), (c,f).)
 */
export type AffineMatrix = readonly [
  readonly [number, number, number],
  readonly [number, number, number],
]

export interface CalibrateRequest {
  /** Batches to calibrate from; which ones is the orchestrator's policy (see CalibrationPolicy). */
  readonly batches: readonly Batch[]
  readonly numberFormat: NumberFormat
}

export interface CalibrationFailure {
  readonly position: number
  readonly focusStep: number
  readonly message: string
}

export interface CalibrateResult {
  /** Averaged matrices, index = focus step. transforms[referenceStep] is the identity. */
  readonly transforms: readonly AffineMatrix[]
  /** floor(stackSize / 2), as in OS3. */
  readonly referenceStep: number
  readonly stackSize: number
  readonly imageWidth: number
  readonly imageHeight: number
  /** Unaveraged matrices per input batch (same order as request.batches), for diagnostics. */
  readonly perBatchTransforms: readonly (readonly AffineMatrix[])[]
  /** ECC failures. OS3 ignores them silently; we record them so the UI can warn. */
  readonly failures: readonly CalibrationFailure[]
}

/** How the orchestrator picks the batches it passes to calibrate(). */
export type CalibrationPolicy =
  /** Completed scans: batchCount batches evenly spaced over all positions (OS3-equivalent). */
  | { readonly kind: 'spread'; readonly batchCount: number }
  /** Live, default: the first batchCount positions to complete, in capture order. */
  | { readonly kind: 'leading'; readonly batchCount: number }
  /** Live, optional: a separate short scan with identical camera/focus settings before the main scan. */
  | { readonly kind: 'calibration-scan'; readonly positions: number; readonly scanIndex: number }

/**
 * Calibration record as persisted in the storage target (calibration_scanXX.json).
 * Superset of OS3's file format: `project`, `scan_index` and `transforms` keep OS3's
 * names and meaning, everything else is additional.
 */
export interface CalibrationRecord {
  readonly project: string
  readonly scan_index: number
  readonly transforms: readonly AffineMatrix[]
  readonly formatVersion: 1
  readonly referenceStep: number
  readonly stackSize: number
  readonly imageWidth: number
  readonly imageHeight: number
  readonly policy: CalibrationPolicy
  /** Positions of the batches the transforms were computed from. */
  readonly sourcePositions: readonly number[]
  readonly failures: readonly CalibrationFailure[]
  readonly algorithm: {
    readonly name: 'os3-ecc-affine'
    readonly os3Version: string
    readonly downscale: 0.25
  }
  /** ISO 8601 timestamp. */
  readonly createdAt: string
}

// ---------------------------------------------------------------------------
// Merging
// ---------------------------------------------------------------------------

/**
 * Tiling of the OUTPUT image (reference frame).
 * 'grid': cores of tileWidth x tileHeight starting at (0, 0), last row/column clipped;
 * each tile is processed as its core expanded by `overlap` on every side (clipped to
 * the image), and only the core is written to the result.
 * Constraints: tileWidth, tileHeight, overlap are multiples of 4; overlap >= 16.
 */
export type TilePlan =
  | { readonly kind: 'untiled' }
  | {
      readonly kind: 'grid'
      readonly tileWidth: number
      readonly tileHeight: number
      readonly overlap: number
    }

/**
 * Number format of decoded pixels. Always explicit, never assumed.
 * Interface version 1 backends support bitsPerChannel 8 only; 16 is reserved
 * for the helper+server expansion. Internal math is floating point regardless.
 */
export interface NumberFormat {
  readonly bitsPerChannel: 8 | 16
  readonly channels: 3
}

export interface OutputEncoding {
  readonly format: 'jpeg'
  /** 1..100; OS3 uses 90. */
  readonly quality: number
}

/**
 * Where the encoded result goes. Jobs never carry absolute paths.
 * - 'directory-handle': browser backends, File System Access API (Chromium, secure context only).
 * - 'download':         browser fallback, one download per file. Cannot be verified.
 * - 'helper-directory': the helper writes below its own configured output root.
 * - 'memory':           nothing is written; the blob is returned (mock backend, tests).
 */
export type StorageTarget =
  | { readonly kind: 'directory-handle'; readonly handle: FileSystemDirectoryHandle }
  | { readonly kind: 'download' }
  | { readonly kind: 'helper-directory' }
  | { readonly kind: 'memory' }

export interface OutputSpec {
  /** Path relative to the storage target root, "/"-separated, e.g. "MyProject/scan01/stacked_scan01_004.jpg". */
  readonly relativePath: string
  readonly encoding: OutputEncoding
  readonly target: StorageTarget
}

export interface StackJob {
  readonly batch: Batch
  /** From the calibration record; index = focus step; length = stackSize. */
  readonly transforms: readonly AffineMatrix[]
  readonly tilePlan: TilePlan
  readonly numberFormat: NumberFormat
  readonly output: OutputSpec
}

/**
 * - 'verified':   written, then re-opened through the storage target and compared
 *                 byte-for-byte (length + content) with the encoded buffer. Only this
 *                 state allows deleting the originals on the Pi.
 * - 'unverified': handed over but not checkable (download fallback).
 * - 'returned':   memory target.
 */
export type Delivery =
  | { readonly kind: 'verified'; readonly relativePath: string }
  | { readonly kind: 'unverified'; readonly relativePath: string }
  | { readonly kind: 'returned'; readonly blob: Blob }

export interface StackResult {
  readonly position: number
  readonly width: number
  readonly height: number
  readonly byteLength: number
  /** Lowercase hex SHA-256 of the encoded file, when the backend can compute it (else null). */
  readonly sha256: string | null
  readonly delivery: Delivery
  readonly timingsMs: {
    readonly fetch: number
    readonly decode: number
    readonly merge: number
    readonly encode: number
    readonly write: number
  }
}

// ---------------------------------------------------------------------------
// Backend
// ---------------------------------------------------------------------------

export type BackendId = 'mock' | 'pyodide' | 'webgpu' | 'helper'

export interface BackendCapabilities {
  readonly id: BackendId
  readonly interfaceVersion: typeof COMPUTE_INTERFACE_VERSION
  readonly bitsPerChannel: readonly NumberFormat['bitsPerChannel'][]
  readonly imageSourceKinds: readonly ImageSource['kind'][]
  readonly storageTargetKinds: readonly StorageTarget['kind'][]
  /** Tile plan the backend works best with; the orchestrator uses it unless overridden. */
  readonly preferredTilePlan: TilePlan
  /** Jobs the backend accepts concurrently (queue depth beyond that is the orchestrator's). */
  readonly maxConcurrentJobs: number
}

export type ProgressPhase = 'fetch' | 'decode' | 'align' | 'merge' | 'encode' | 'write' | 'verify'

export interface Progress {
  readonly phase: ProgressPhase
  readonly done: number
  readonly total: number
}

export interface JobControl {
  readonly signal?: AbortSignal
  readonly onProgress?: (progress: Progress) => void
}

export type ComputeErrorCode =
  | 'aborted'
  | 'unsupported'
  | 'invalid-job'
  | 'fetch-failed'
  | 'decode-failed'
  | 'size-mismatch'
  | 'write-failed'
  | 'verify-failed'
  | 'out-of-memory'
  | 'internal'

/** Shape of errors backends reject with (as an Error subclass carrying these fields). */
export interface ComputeErrorInfo {
  readonly code: ComputeErrorCode
  readonly message: string
  readonly retryable: boolean
}

/** What every compute path (mock, Pyodide, WebGPU, helper) implements. */
export interface ComputeBackend {
  init(): Promise<BackendCapabilities>
  calibrate(request: CalibrateRequest, control?: JobControl): Promise<CalibrateResult>
  stackBatch(job: StackJob, control?: JobControl): Promise<StackResult>
  /** Optional hint: start fetching these photos now (live mode). May be a no-op. */
  prefetch?(images: readonly StackImage[]): void
  dispose(): Promise<void>
}

// ---------------------------------------------------------------------------
// Helper detection (Step 6a) — wire protocol in ./helper-http-api.md
// ---------------------------------------------------------------------------

export const DEFAULT_HELPER_BASE_URL = 'http://127.0.0.1:8742' as const

export type HelperProbeResult =
  | { readonly state: 'absent' }
  | { readonly state: 'incompatible'; readonly interfaceVersion: number; readonly helperVersion: string }
  | { readonly state: 'unpaired'; readonly helperVersion: string }
  | { readonly state: 'paired'; readonly helperVersion: string; readonly outputRoot: string }
