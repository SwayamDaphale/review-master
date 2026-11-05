// Sample admin data (clearly fictional). Replaced by /api/v1/admin/* once the backend exists.

export interface ModelParam {
  key: string;
  name: string;
  weight: number | null;
}
export interface EvalModel {
  id: string;
  category: string;
  version: string;
  status: 'draft' | 'published';
  params: ModelParam[];
  domainApproved: boolean;
  engineeringApproved: boolean;
}

const p = (key: string, name: string): ModelParam => ({ key, name, weight: null });

export const MODELS_SEED: EvalModel[] = [
  {
    id: 'm-smartphone',
    category: 'Smartphones',
    version: '1-draft',
    status: 'draft',
    domainApproved: false,
    engineeringApproved: false,
    params: [
      p('performance', 'Performance'),
      p('battery_charging', 'Battery and charging'),
      p('camera', 'Camera'),
      p('display', 'Display'),
      p('software_updates', 'Software and updates'),
      p('build_durability', 'Build and durability'),
      p('connectivity_features', 'Connectivity and features'),
    ],
  },
  {
    id: 'm-laptop',
    category: 'Laptops',
    version: '1-draft',
    status: 'draft',
    domainApproved: false,
    engineeringApproved: false,
    params: [
      p('cpu', 'CPU'),
      p('gpu', 'GPU'),
      p('ram_storage', 'RAM and storage'),
      p('display', 'Display'),
      p('battery', 'Battery'),
      p('thermal_sustained', 'Thermals and sustained performance'),
      p('build_portability', 'Build and portability'),
      p('connectivity_upgradeability', 'Connectivity and upgradeability'),
    ],
  },
  {
    id: 'm-ssd',
    category: 'External SSDs',
    version: '1-draft',
    status: 'draft',
    domainApproved: false,
    engineeringApproved: false,
    params: [
      p('sequential_rw', 'Sequential read and write'),
      p('sustained_write', 'Sustained write'),
      p('capacity', 'Capacity'),
      p('interface_compat', 'Interface and compatibility'),
      p('durability_thermal', 'Durability and thermal'),
      p('warranty_endurance', 'Warranty and endurance'),
      p('portability_build', 'Portability and build'),
    ],
  },
];

export interface MappingItem {
  id: string;
  listing: string;
  title: string;
  suggestion: string;
  state: 'probable' | 'ambiguous';
  reason: string;
  status: 'pending' | 'confirmed' | 'rejected';
}

export const MAPPINGS_SEED: MappingItem[] = [
  {
    id: 'map-1',
    listing: 'Amazon India B0FQFJKBVY',
    title: 'Apple iPhone 17 Pro Max 1 TB: 17.42 cm (6.9") Display with Promotion, A19 Pro Chip',
    suggestion: 'Apple iPhone 17 Pro Max (1 TB)',
    state: 'probable',
    reason: 'Processor read as "Others" and battery was not captured.',
    status: 'pending',
  },
  {
    id: 'map-2',
    listing: 'Amazon India (sample listing 2)',
    title: 'Sample Phone C 5G (title does not state memory or storage)',
    suggestion: 'Sample Phone C (two variants possible)',
    state: 'ambiguous',
    reason: 'Memory and storage are missing from the title, so two variants fit.',
    status: 'pending',
  },
  {
    id: 'map-3',
    listing: 'Amazon India (sample listing 3)',
    title: 'Sample Portable SSD (capacity missing)',
    suggestion: 'Sample Portable SSD 1 TB or 2 TB',
    state: 'ambiguous',
    reason: 'Capacity was not found on the page.',
    status: 'pending',
  },
];

export interface ModerationItem {
  id: string;
  target: string;
  author: string;
  text: string;
  flags: string[];
  state: 'pending' | 'approved' | 'rejected' | 'flagged';
}

export const MODERATION_SEED: ModerationItem[] = [
  {
    id: 'fb-1',
    target: 'Sample Phone C, 12 GB / 256 GB',
    author: 'reviewer-1042',
    text: 'Battery easily lasts a day and a half with normal use. Camera is great outdoors.',
    flags: [],
    state: 'pending',
  },
  {
    id: 'fb-2',
    target: 'Sample Phone C, 12 GB / 256 GB',
    author: 'reviewer-2210',
    text: 'Best phone ever, buy now, five stars, amazing, best phone ever.',
    flags: ['Wording repeats in several other reviews this week'],
    state: 'flagged',
  },
  {
    id: 'fb-3',
    target: 'Sample Laptop A, 16 GB / 512 GB',
    author: 'reviewer-0877',
    text: 'Fan gets loud when exporting video. Keyboard is nice though.',
    flags: [],
    state: 'pending',
  },
];

export type Role = 'consumer' | 'public_reviewer' | 'expert_reviewer' | 'admin' | 'api_consumer';
export const ROLES: Role[] = ['consumer', 'public_reviewer', 'expert_reviewer', 'admin', 'api_consumer'];

export interface AdminUser {
  id: string;
  name: string;
  email: string;
  role: Role;
}

export const USERS_SEED: AdminUser[] = [
  { id: 'u-1', name: 'Asha Verma', email: 'asha@example.com', role: 'consumer' },
  { id: 'u-2', name: 'Rohan Iyer', email: 'rohan@example.com', role: 'public_reviewer' },
  { id: 'u-3', name: 'Dr. Meera Nair', email: 'meera@example.com', role: 'expert_reviewer' },
  { id: 'u-4', name: 'Platform Admin', email: 'admin@example.com', role: 'admin' },
  { id: 'u-5', name: 'Partner API client', email: 'api@example.com', role: 'api_consumer' },
];

export interface Integration {
  name: string;
  status: 'healthy' | 'degraded' | 'not_connected';
  detail: string;
}

export const INTEGRATIONS: Integration[] = [
  { name: 'Amazon India browser extension', status: 'healthy', detail: 'Version 1.0.0 captures smartphone pages on request.' },
  { name: 'Backend API (FastAPI)', status: 'not_connected', detail: 'Not built yet. The app is using sample data.' },
  { name: 'Database (PostgreSQL)', status: 'not_connected', detail: 'Not created yet. Settings and actions are stored in this browser.' },
  { name: 'LLM gateway (LiteLLM)', status: 'not_connected', detail: 'Summaries shown are written by hand as samples.' },
];

/** What still blocks publishing a model version. Mirrors the rules in architecture/EVALUATION_MODEL_SPECS.md. */
export function modelBlockers(model: EvalModel): string[] {
  const out: string[] = [];
  const unset = model.params.filter((p) => p.weight === null).length;
  if (unset > 0) out.push(`${unset} of ${model.params.length} weights are not set`);
  else {
    const sum = model.params.reduce((a, p) => a + (p.weight ?? 0), 0);
    if (Math.abs(sum - 1) > 0.0001) out.push(`Weights add up to ${sum.toFixed(2)}, not 1.00`);
  }
  if (!model.domainApproved) out.push('Domain expert approval is missing');
  if (!model.engineeringApproved) out.push('Engineering approval is missing');
  return out;
}
