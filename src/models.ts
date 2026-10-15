export type RouteMode = "auto" | "manual" | "off";

export interface SkillMetadata {
  name: string;
  description: string;
  source?: string;
  location?: string;
  domains?: string[];
  resource_types?: string[];
  operations?: string[];
  triggers?: string[];
  not_for?: string[];
  related_skills?: string[];
  dependencies?: string[];
  exclusive_group?: string;
  priority?: number;
  version?: string;
}

export interface RouteRequest {
  text: string;
  mode?: RouteMode;
  explicit_skills?: string[];
  allow_external_search?: boolean;
  max_skills?: number;
  semantic?: boolean;
}

export interface SkillSelection {
  name: string;
  score: number;
  reason: string;
}

export interface RouteResult {
  mode: RouteMode;
  action: string;
  selected: string[];
  selections: SkillSelection[];
  confidence: number;
  reason: string;
  external_search: boolean;
  install_required: boolean;
  warnings: string[];
  external_candidates: Record<string, unknown>[];
  plan: Record<string, unknown>[];
}

export interface SemanticCandidate {
  name: string;
  confidence: number;
  reason: string;
}

export interface SemanticProvider {
  rank(task: string, candidates: SkillMetadata[]): Promise<SemanticCandidate[]>;
}
