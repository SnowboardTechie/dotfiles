const DISCOVERY_TIMEOUT_MS = 1000;
const DEFAULT_MODEL_LIMIT = {
  context: 65536,
  output: 16384,
};

export const OllamaModelsPlugin = async () => ({
  config: async (config) => {
    const provider = config.provider?.ollama;
    const baseURL = provider?.options?.baseURL;

    if (typeof baseURL !== "string") {
      return;
    }

    try {
      const response = await fetch(`${baseURL.replace(/\/+$/, "")}/models`, {
        signal: AbortSignal.timeout(DISCOVERY_TIMEOUT_MS),
      });

      if (!response.ok) {
        return;
      }

      const payload = await response.json();
      const modelIDs = [
        ...new Set(
          (Array.isArray(payload?.data) ? payload.data : [])
            .map((model) => model?.id)
            .filter((id) => typeof id === "string" && id.length > 0),
        ),
      ];

      if (modelIDs.length === 0) {
        return;
      }

      const configuredModels = provider.models ?? {};
      provider.models = Object.fromEntries(
        modelIDs.map((id) => [
          id,
          configuredModels[id] ?? { name: id, limit: DEFAULT_MODEL_LIMIT },
        ]),
      );
    } catch {
      // Keep the static model list when Studio is unavailable.
    }
  },
});
