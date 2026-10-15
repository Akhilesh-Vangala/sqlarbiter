export const state = {
  capability: null,
  account: null,
  user: null,
  entries: [],
  projects: [],
  storageError: "",
  route: location.pathname,
  draft: null,
  stage: 0,
  issues: null,
  busy: false,
  controller: null,
  previewOffset: 0,
  previewSearch: "",
  previewRows: [],
};
export function newDraft() {
  return {
    id: crypto.randomUUID(),
    title: "Untitled investigation",
    projectId: "",
    createdAt: new Date().toISOString(),
    filename: "",
    csv: "",
    mapping: {},
    options: { unit: "dollars" },
    profile: null,
    report: null,
    stage: 0,
    sourceKind: "upload",
    storage: "memory",
    dirty: true,
  };
}
export function payload() {
  return {
    csv: state.draft.csv,
    mapping: { ...state.draft.mapping },
    options: { ...state.draft.options },
  };
}
