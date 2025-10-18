import { temporaryChatEnabled } from "$lib/stores";

export const modelsInfo = {
	"Claude 4.5 Haiku": {
		context_window: '200K',
		costFactor: 1,
		credit_multiple: 6,
		description: 'Claude Haiku 4.5 is fast and cost-effective. Well suited for simpler queries and quick responses. For very complex tasks or in-depth analyses, other models are better suited.',
		hosted_in: 'EU',
		included: true,
		intelligence_score: 3,
		knowledge_cutoff: '2025-02-28',
		multimodal: true,
		organization: 'Anthropic',
		reasoning: false,
		research: false,
		speed: 2.5,
		zdr: false,
	},
	"Claude Sonnet 4.5": {
		context_window: '200K',
		costFactor: 3,
		credit_multiple: 22,
		description: "Anthropic's most powerful model, with industry-leading capabilities in programming, computer use, cybersecurity, and working with office files such as spreadsheets",
		hosted_in: 'EU',
		included: true,
		intelligence_score: 3,
		knowledge_cutoff: '2025-01-01',
		multimodal: true,
		organization: 'Anthropic',
		reasoning: false,
		research: false,
		speed: 1.5,
		zdr: false,
	},
	"Google 2.5 Flash": {
		context_window: '1M',
		costFactor: 0,
		credit_multiple: 1,
		description: "A balanced model with good reasoning and multimodal capabilities. Optimal price-performance.",
		hosted_in: 'EU',
		included: true,
		intelligence_score: 2.5,
		knowledge_cutoff: '2025-01-31',
		multimodal: false,
		organization: 'Google',
		reasoning: false,
		research: false,
		speed: 2,
		zdr: true,
	},
	"Google 2.5 Pro": {
		context_window: '1M',
		costFactor: 2,
		credit_multiple: 15,
		description: "The most powerful Gemini with top reasoning, 1M token context, and comprehensive multimodality. Ideal for complex problems.",
		hosted_in: 'EU',
		included: true,
		intelligence_score: 3,
		knowledge_cutoff: '2025-01-31',
		multimodal: false,
		organization: 'Google',
		reasoning: false,
		research: false,
		speed: 2,
		zdr: true,
	},
	"GPT o3": {
		organization: 'OpenAI',
		context_window: '200K',
		costFactor: 1.5,
		credit_multiple: 12,
		description: "Strongest reasoning model for mathematics, science and complex problem solving.",
		hosted_in: 'EU',
		included: false,
		intelligence_score: 3.5,
		knowledge_cutoff: '2024-05-31',
		multimodal: false,
		reasoning: false,
		research: false,
		speed: 1.5,
		zdr: false,
	},
	"GPT o4-mini": {
		context_window: '200K',
		costFactor: 1,
		credit_multiple: 7,
		description: "Fast, inexpensive reasoning model with strengths in coding and visual tasks.",
		hosted_in: 'EU',
		included: true,
		intelligence_score: 3,
		knowledge_cutoff: '2024-05-31',
		multimodal: false,
		organization: 'OpenAI',
		reasoning: false,
		research: false,
		speed: 3,
		zdr: false,
	},
	"GPT-5": {
		context_window: '400K',
		costFactor: 2,
		credit_multiple: 0,
		description: "OpenAI's flagship model for coding, reasoning, and agent tasks. Highest reasoning capabilities with moderate speed for complex domains.",
		hosted_in: 'EU',
		included: true,
		intelligence_score: 3.5,
		knowledge_cutoff: '2024-10-01',
		multimodal: true,
		organization: 'OpenAI',
		reasoning: true,
		research: false,
		speed: 2.5,
		zdr: false,
	},
	"GPT-5 mini": {
		context_window: '400K',
		costFactor: 0.5,
		credit_multiple: 0,
		description: "A faster, cost-effective GPT-5 version for clearly defined tasks. High reasoning capabilities at a reduced price for precise prompts.",
		hosted_in: 'EU',
		included: true,
		intelligence_score: 3,
		knowledge_cutoff: '2024-04-01',
		multimodal: true,
		organization: 'OpenAI',
		reasoning: true,
		speed: 4.5,
		zdr: false,
	},
	"GPT-5 nano": {
		context_window: '400K',
		costFactor: 0,
		credit_multiple: 0,
		description: "Fastest and most affordable GPT-5 model. Optimized for summarization and classification with average reasoning capabilities.",
		hosted_in: 'EU',
		included: true,
		intelligence_score: 2.5,
		knowledge_cutoff: '2024-01-04',
		multimodal: true,
		organization: 'OpenAI',
		reasoning: true,
		speed: 5,
		zdr: false,
	},
	"Grok 4": {
		context_window: '256K',
		costFactor: 3,
		credit_multiple: 22,
		description: "xAI's most advanced model with superior reasoning skills and distinctive communication style.",
		hosted_in: 'US',
		included: true,
		intelligence_score: 3.5,
		knowledge_cutoff: null,
		multimodal: false,
		organization: 'xAI',
		reasoning: false,
		research: false,
		speed: 2.5,
		zdr: false,
	},
	"Mistral Large 2": {
		context_window: null,
		costFactor: 1,
		credit_multiple: 9,
		description: 'Great for basic tasks.',
		hosted_in: 'EU',
		included: true,
		intelligence_score: 1.5,
		knowledge_cutoff: null,
		multimodal: false,
		organization: 'Mistral',
		reasoning: false,
		research: false,
		speed: 1.0,
		zdr: false,
	},
	"Perplexity Sonar Deep Research": {
		context_window: null,
		costFactor: 0,
		credit_multiple: 12,
		description: 'Deep research & analysis.',
		hosted_in: 'US',
		included: true,
		intelligence_score: 1.0,
		knowledge_cutoff: null,
		multimodal: false,
		organization: 'Perplexity',
		reasoning: false,
		research: true,
		speed: 1.0,
		zdr: false,
	},
	"Perplexity Sonar Pro": {
		context_window: null,
		costFactor: 0,
		credit_multiple: 22,
		description: 'Balanced general-purpose performance.',
		hosted_in: 'US',
		included: true,
		intelligence_score: 2.5,
		knowledge_cutoff: null,
		multimodal: false,
		organization: 'Perplexity',
		reasoning: false,
		research: true,
		speed: 1.0,
		zdr: false,
	},
	"Perplexity Sonar Reasoning Pro": {
		context_window: null,
		costFactor: 0,
		credit_multiple: 12,
		description: 'Advanced reasoning capabilities.',
		hosted_in: 'US',
		included: true,
		intelligence_score: 1.5,
		knowledge_cutoff: null,
		multimodal: false,
		organization: 'Perplexity',
		reasoning: false,
		research: true,
		speed: 1.0,
		zdr: false,
	},
};

export const mapModelsToOrganizations = (modelsInfo) => {
	const organizations = {};

	for (const [modelName, modelData] of Object.entries(modelsInfo)) {
		const { organization, description } = modelData;
		if(organization === "Deep Seek") {
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
        const kept = models.filter(m => allowed.has(normalize(m)));
        return [org, kept];
      })
      .filter(([, models]) => models.length > 0) 
  );
}
