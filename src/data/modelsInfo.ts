export const mapModelsToOrganizations = (modelsInfo) => {
	const organizations = {};

	for (const [modelName, modelData] of Object.entries(modelsInfo)) {
		const { organization } = modelData as any;
		if (organization === "Deep Seek") {
			continue;
		}

		if (!organizations[organization]) {
			organizations[organization] = [];
		}

		organizations[organization].push(modelName);
	}

	return organizations;
};

export function filterCatalog(
  catalog,
  availableModels,
  { caseInsensitive = false, trim = true } = {}
) {
  const norm = s => (trim ? String(s).trim() : String(s));
  const normalize = caseInsensitive ? s => norm(s).toLowerCase() : s => norm(s);

  const allowed = new Set(availableModels.map(normalize));

  return Object.fromEntries(
    Object.entries(catalog)
      .map(([org, models]) => {
        const kept = (models as string[]).filter(m => allowed.has(normalize(m)));
        return [org, kept];
      })
      .filter(([, models]) => (models as string[]).length > 0)
  );
}
