import { temporaryChatEnabled } from "$lib/stores";

export const modelsInfo = {
	"Claude 4.5 Haiku": {
		context_window: '200K',
		costFactor: 1,
		description: 'Claude Haiku 4.5 is fast and cost-effective. Well suited for simpler requests and quick responses. For very complex tasks or in-depth analyses, other models are better suited.',
		hosted_in: 'EU',
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
		description: "Anthropic's most powerful model, with industry-leading capabilities in programming, computer use, cybersecurity, and working with office files like spreadsheets.",
		hosted_in: 'EU',
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
		description: "Balanced model with good reasoning and multimodal capabilities. Optimal price-performance ratio.",
		hosted_in: 'EU',
		intelligence_score: 2.5,
		knowledge_cutoff: '2025-01-31',
		multimodal: true,
		organization: 'Google',
		reasoning: false,
		research: false,
		speed: 2,
		zdr: true,
	},
	"Google 2.5 Pro": {
		context_window: '1M',
		costFactor: 2,
		description: "Strongest Gemini with top-tier reasoning, a 1M-token context window, and comprehensive multimodality. Ideal for complex problems.",
		hosted_in: 'EU',
		intelligence_score: 3,
		knowledge_cutoff: '2025-01-31',
		multimodal: true,
		organization: 'Google',
		reasoning: true,
		research: false,
		speed: 2,
		zdr: true,
	},
	"GPT o3": {
		context_window: '200K',
		costFactor: 1.5,
		description: "Strongest reasoning model for math, science, and complex problem solving.",
		hosted_in: 'EU',
		intelligence_score: 3.5,
		knowledge_cutoff: '2024-05-31',
		multimodal: false,
		organization: 'OpenAI',
		reasoning: true,
		research: false,
		speed: 1.5,
		zdr: false,
	},
	"GPT o4-mini": {
		context_window: '200K',
		costFactor: 1,
		description: "Fast, affordable reasoning model with strengths in coding and visual tasks.",
		hosted_in: 'EU',
		intelligence_score: 3,
		knowledge_cutoff: '2024-05-31',
		multimodal: false,
		organization: 'OpenAI',
		reasoning: true,
		research: false,
		speed: 3,
		zdr: false,
	},
	"GPT-5": {
		context_window: '400K',
		costFactor: 2,
		description: "OpenAI's flagship model for coding, reasoning, and agent tasks. Highest reasoning capabilities with moderate speed for complex domains.",
		hosted_in: 'EU',
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
		description: "Offers a balanced combination of response quality and speed. Well suited for everyday questions, creative tasks, and explanations of medium complexity. For very complex analyses or highly specialized expert questions, more powerful models are better suited.",
		hosted_in: 'EU',
		intelligence_score: 3,
		knowledge_cutoff: '2024-04-01',
		multimodal: true,
		organization: 'OpenAI',
		reasoning: true,
		research: false,
		speed: 4.5,
		zdr: false,
	},
	"GPT-5 nano": {
		context_window: '400K',
		costFactor: 0,
		description: "Fast model for simple tasks like summarization and classification. Solid response quality with average reasoning capabilities. For complex analyses or deep logic, other models are better suited.",
		hosted_in: 'EU',
		intelligence_score: 2.5,
		knowledge_cutoff: '2024-01-04',
		multimodal: true,
		organization: 'OpenAI',
		reasoning: true,
		research: false,
		speed: 5,
		zdr: false,
	},
	"Grok 4": {
		context_window: '256K',
		costFactor: 3,
		description: "xAI's most advanced model with exceptional reasoning capabilities and a distinctive communication style.",
		hosted_in: 'EU',
		intelligence_score: 3.5,
		knowledge_cutoff: null,
		multimodal: false,
		organization: 'xAI',
		reasoning: true,
		research: false,
		speed: 2.5,
		zdr: false,
	},
	"Mistral Large 2": {
		context_window: '128K',
		costFactor: 1,
		description: 'Strong performance in code, mathematics, and logic. Supports many languages and delivers precise answers. Ideal for technical queries and programming; less flexible for creative tasks.',
		hosted_in: 'EU',
		intelligence_score: 1.5,
		knowledge_cutoff: null,
		multimodal: false,
		organization: 'Mistral',
		reasoning: false,
		research: false,
		speed: 0,
		zdr: false,
	},
	"Perplexity Sonar Deep Research": {
		context_window: '200K',
		costFactor: 0,
		description: 'Deep Research generates detailed research reports in 2–4 minutes. Suitable for complex tasks in finance, marketing, technology, product research, and travel planning. Not suitable for simple questions due to higher cost and longer turnaround time.',
		hosted_in: 'US',
		intelligence_score: 0,
		knowledge_cutoff: null,
		multimodal: false,
		organization: 'Perplexity',
		reasoning: true,
		research: true,
		speed: 0,
		zdr: false,
	},
	"Perplexity Sonar Pro": {
		context_window: '127K',
		costFactor: 0,
		description: 'Provides high-quality answers with reliable source citations via direct internet access. Ideal for knowledge-intensive questions and structured research. For simple questions or time-sensitive requests, lighter-weight models are more efficient.',
		hosted_in: 'US',
		intelligence_score: 1.5,
		knowledge_cutoff: null,
		multimodal: false,
		organization: 'Perplexity',
		reasoning: false,
		research: true,
		speed: 0,
		zdr: false,
	},
	"Perplexity Sonar Reasoning Pro": {
		context_window: '200K',
		costFactor: 0,
		description: 'Strong reasoning model for complex problem solving. Suitable for multi-step analyses, legal and financial questions, and deep logic. Not suitable for simple questions due to longer turnaround time.',
		hosted_in: 'US',
		intelligence_score: 2.5,
		knowledge_cutoff: null,
		multimodal: false,
		organization: 'Perplexity',
		reasoning: true,
		research: true,
		speed: 0,
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
