export type Role = 'professor' | 'ta' | 'admin'
export type View = 'dashboard' | 'grade' | 'rubrics' | 'submissions' | 'crowdmark' | 'settings'

export interface Level {
  label: string
  points: number
  description: string
}

export interface Criterion {
  name: string
  points: number
  description: string
  levels: Level[]
}

export interface Rubric {
  id: string
  name: string
  assignment: string
  version: string
  createdBy: string
  updatedAt: number
  totalPoints: number
  criteria: Criterion[]
  instructions?: string
}

export type SubmissionStatus = 'graded' | 'review' | 'pending' | 'error'

export interface CriterionResult {
  name: string
  earned: number
  max: number
  level?: string
  note: string
}

export interface Submission {
  id: string
  student: string
  studentId: string
  email: string
  assignment: string
  rubricId: string
  rubricName: string
  file: string
  fileSize: number
  fileKind: 'text' | 'pdf' | 'scan' | 'image'
  content: string
  score: number | null
  total: number
  aiScore: number | null
  status: SubmissionStatus
  gradedBy: string
  confidence: number | null
  criteria: CriterionResult[]
  summary: string
  flagReason: string
  similarity?: { with: string; withName: string; percent: number } | null
  submittedAt: number
  gradedAt: number | null
  updatedAt: number
  approvedBy: string | null
  approvedAt: number | null
  overridden: boolean
  error?: string
  uploadedBy: string
  /** Set by the server while the file waits for or is being graded by the model. */
  queueState?: 'ocr' | 'waiting' | 'grading' | null
  batchId?: string
  options?: { flagLow: boolean; detailed: boolean; plagiarism: boolean }
  storedFile?: string
  model?: string
}

export interface RosterEntry {
  name: string
  email: string
  studentId: string
  utorid: string
}

export interface CourseSettings {
  code: string
  name: string
  term: string
  instructor: string
  enrollment: number
  currentAssignment: string
  threshold: number
  autoApprove: boolean
  requireSignoff: boolean
  plagiarism: boolean
  minutesPerManualGrade: number
  crowdmarkCourse: string
  institution: string
  roster: RosterEntry[]
  /** System prompt sent to the fine-tuned model with every request. */
  systemPrompt: string
  /** Submission text is cut to this many characters to fit the model's context window. */
  maxInputChars: number
  updatedAt: number
}

export interface ModelStatus {
  online: boolean
  lastSeen: number | null
  model: string | null
  slurmJobId: string | null
  node: string | null
  endsAt: number | null
  waiting: number
  grading: number
}

export interface Member {
  id: string
  name: string
  email: string
  role: Role
  status: 'active' | 'invited'
  lastLogin: number | null
}

export type ActivityType = 'grade' | 'rubric' | 'export' | 'flag' | 'system'

export interface Activity {
  id: string
  type: ActivityType
  title: string
  body: string
  at: number
  by: string
}

export interface ExportRecord {
  id: string
  assignment: string
  count: number
  excluded: number
  at: number
  by: string
  filename: string
}

export interface TeamDoc {
  members: Record<string, Role>
}

export interface Person {
  id: string
  name: string
  email: string | null
  avatarUrl: string | null
  color: string
}
