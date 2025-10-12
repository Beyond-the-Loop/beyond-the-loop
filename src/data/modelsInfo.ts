import { temporaryChatEnabled } from "$lib/stores";

export const modelsInfo = {
	"Claude 3.5 Haiku": {
		organization: 'Anthropic',
		hosted_in: 'EU',
		description: 'Fastest Claude model. Cost-effective with solid coding and reasoning capabilities. Ideal for real-time applications.',
		context_window: '200K',
		knowledge_cutoff: null,
		intelligence_score: 2,
		speed: 1.5,
		multimodal: false,
		reasoning: false,
		included: true,
		credit_multiple: 6,
		research: false,
		costFactor: 1
	},
	"Claude Opus 4.1": {
		organization: 'Anthropic',
		hosted_in: 'US',
		description: "Anthropic's hybrid reasoning model with 200K context for complex coding and agent tasks. Advanced thinking abilities with visible reasoning steps.",
		context_window: '200K',
		knowledge_cutoff: null,
		intelligence_score: 4,
		speed: 3,
		multimodal: true,
		reasoning: true,
		costFactor: 5
	},
	"Claude Sonnet 4.5": {
		organization: 'Anthropic',
		hosted_in: 'EU',
		description: "Anthropic's most powerful model, with industry-leading capabilities in programming, computer use, cybersecurity, and working with office files such as spreadsheets",
		context_window: '200K',
		knowledge_cutoff: '2025-01-01',
		intelligence_score: 4,
		speed: 1.5,
		multimodal: true,
		reasoning: false,
		included: true,
		credit_multiple: 22,
		research: false,
		costFactor: 3
	},
	"Google 2.5 Flash": {
		organization: 'Google',
		hosted_in: 'EU',
		description: "A balanced model with good reasoning and multimodal capabilities. Optimal price-performance.",
		context_window: '1M',
		knowledge_cutoff: '2025-01-31',
		intelligence_score: 4,
		speed: 2.5,
		multimodal: true,
		reasoning: true,
		included: true,
		credit_multiple: 1,
		research: false,
		zdr: true,
		costFactor: 0.5
	},
	"Google 2.5 Pro": {
		organization: 'Google',
		hosted_in: 'EU',
		description: "The most powerful Gemini with top reasoning, 1M token context, and comprehensive multimodality. Ideal for complex problems.",
		context_window: '1M',
		knowledge_cutoff: '2025-01-31',
		intelligence_score: 4.5,
		speed: 2.5,
		multimodal: true,
		reasoning: true,
		included: true,
		credit_multiple: 15,
		research: false,
		zdr: true,
		costFactor: 2
	},
	"GPT o3": {
		organization: 'OpenAI',
		hosted_in: 'EU',
		description: "Strongest reasoning model for mathematics, science and complex problem solving.",
		context_window: '200K',
		knowledge_cutoff: '2024-05-31',
		intelligence_score: 4,
		speed: 2,
		multimodal: true,
		reasoning: true,
		included: true,
		credit_multiple: 12,
		research: false,
		costFactor: 2
	},
	"GPT o4-mini": {
		organization: 'OpenAI',
		hosted_in: 'EU',
		description: "Fast, inexpensive reasoning model with strengths in coding and visual tasks.",
		context_window: '200K',
		knowledge_cutoff: '2024-05-31',
		intelligence_score: 4,
		speed: 3.5,
		multimodal: true,
		reasoning: true,
		included: true,
		credit_multiple: 7,
		research: false,
		costFactor: 1
	},
	"GPT-5": {
		organization: 'OpenAI',
		hosted_in: 'EU',
		description: "OpenAI's flagship model for coding, reasoning, and agent tasks. Highest reasoning capabilities with moderate speed for complex domains.",
		context_window: '400K',
		knowledge_cutoff: '2024-10-01',
		intelligence_score: 4.5,
		speed: 3,
		multimodal: true,
		reasoning: true,
		costFactor: 2
	},
	"GPT-5 mini": {
		organization: 'OpenAI',
		hosted_in: 'EU',
		description: "A faster, cost-effective GPT-5 version for clearly defined tasks. High reasoning capabilities at a reduced price for precise prompts.",
		context_window: '400K',
		knowledge_cutoff: '2024-04-01',
		intelligence_score: 4,
		speed: 4.5,
		multimodal: true,
		reasoning: true,
		costFactor: 0.5
	},
	"GPT-5 nano": {
		organization: 'OpenAI',
		hosted_in: 'EU',
		description: "Fastest and most affordable GPT-5 model. Optimized for summarization and classification with average reasoning capabilities.",
		context_window: '400K',
		knowledge_cutoff: '2024-01-04',
		intelligence_score: 3.5,
		speed: 5,
		multimodal: true,
		reasoning: true,
		costFactor: 0.5
	},
	"Grok 4": {
		organization: 'xAI',
		hosted_in: 'US',
		description: "xAI's most advanced model with superior reasoning skills and distinctive communication style.",
		context_window: '256K',
		knowledge_cutoff: '2024-12-31',
		intelligence_score: 4.5,
		speed: 2.5,
		multimodal: true,
		reasoning: false,
		included: true,
		credit_multiple: 22,
		research: false,
		costFactor: 3
	},
	"Mistral Large 2": {
		organization: 'Mistral',
		hosted_in: 'EU',
		description: 'Great for basic tasks.',
		context_window: '128K',
		knowledge_cutoff: '2023-10-01',
		intelligence_score: 4.0,
		speed: 2.0,
		multimodal: false,
		reasoning: false,
		included: true,
		credit_multiple: 9,
		research: false,
		costFactor: null
	},
	"Perplexity Sonar Deep Research": {
		organization: 'Perplexity',
		hosted_in: 'US',
		description: 'Deep research & analysis.',
		context_window: '128K',
		knowledge_cutoff: null,
		intelligence_score: null,
		speed: 1.0,
		multimodal: false,
		reasoning: false,
		included: true,
		credit_multiple: 12,
		research: true,
		costFactor: 5
	},
	"Perplexity Sonar Pro": {
		organization: 'Perplexity',
		hosted_in: 'US',
		description: 'Balanced general-purpose performance.',
		context_window: '200K',
		knowledge_cutoff: null,
		intelligence_score: null,
		speed: 1.0,
		multimodal: false,
		reasoning: false,
		included: true,
		credit_multiple: 22,
		research: true,
		costFactor: 3
	},
	"Perplexity Sonar Reasoning Pro": {
		organization: 'Perplexity',
		hosted_in: 'US',
		description: 'Advanced reasoning capabilities.',
		context_window: '128K',
		knowledge_cutoff: null,
		intelligence_score: null,
		speed: 1.0,
		multimodal: false,
		reasoning: true,
		included: true,
		credit_multiple: 12,
		research: true,
		costFactor: 4
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
