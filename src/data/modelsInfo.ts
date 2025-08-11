export const modelsInfo = {
	'Claude 3.5 Haiku': {
		organization: 'Anthropic',
		hosted_in: 'US',
		description: 'Fastest Claude model. Cost-effective with solid coding and reasoning capabilities. Ideal for real-time applications.',
		context_window: '200K',
		knowledge_cutoff: null,
		intelligence_score: null,
		speed: 3.0,
		multimodal: false,
		reasoning: false,
		included: true,
		credit_multiple: 6,
		research: false
	},
	'Claude Opus 4': {
		organization: 'Anthropic',
		hosted_in: 'US',
		description: "Anthropic's flagship model with superior coding capabilities and tool utilization. Excellent for complex, long-term tasks.",
		context_window: '200K',
		knowledge_cutoff: '2025-05-22',
		intelligence_score: 4.0,
		speed: 2.0,
		multimodal: true,
		reasoning: true,
		included: true,
		credit_multiple: 112,
		research: false
	},
	"Claude Sonnet 4": {
		organization: 'Anthropic',
		hosted_in: 'US',
		description: "Balance of performance and efficiency. Strong coding and reasoning skills with tool support.",
		context_window: '200K',
		knowledge_cutoff: '2025-05-22',
		intelligence_score: 4.5,
		speed: 2.5,
		multimodal: true,
		reasoning: true,
		included: true,
		credit_multiple: 22,
		research: false
	},
	"Claude Opus 4.1": {
		organization: 'Anthropic',
		hosted_in: 'US',
		description: "Anthropic's hybrid reasoning model with 200K context for complex coding and agent tasks. Advanced thinking abilities with visible reasoning steps.",
		context_window: '200K',
		knowledge_cutoff: null,
		intelligence_score: 4.5,
		speed: 3.5,
		multimodal: true,
		reasoning: true
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
		research: false
	},
	"Google 2.5 Flash": {
		organization: 'Google',
		hosted_in: 'EU',
		description: "A balanced model with good reasoning and multimodal capabilities. Optimal price-performance.",
		context_window: '1M',
		knowledge_cutoff: '2025-01-31',
		intelligence_score: 4.0,
		speed: 2.5,
		multimodal: true,
		reasoning: true,
		included: true,
		credit_multiple: 1,
		research: false
	},
	"Google 2.5 Flash-Lite": {
		organization: 'Google',
		hosted_in: 'EU',
		description: "Fast model for reasoning, science, and code. Focus on low latency.",
		context_window: '1M',
		knowledge_cutoff: '2025-01-01',
		intelligence_score: 3.0,
		speed: 1.0,
		multimodal: true,
		reasoning: true,
		included: true,
		credit_multiple: 1,
		research: false
	},
	'Mistral Large 2': {
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
		research: false
	},
	'Pixtral Large': {
		organization: 'Mistral',
		hosted_in: 'EU',
		description: 'Image-text multimodal integration.',
		context_window: '128K',
		knowledge_cutoff: null,
		intelligence_score: null,
		speed: 0.5,
		multimodal: true,
		reasoning: false,
		included: true,
		credit_multiple: 9,
		research: false
	},
	'GPT o3-mini': {
		organization: 'OpenAI',
		hosted_in: 'EU',
		description: 'Optimized for coding & reasoning.',
		context_window: '200K',
		knowledge_cutoff: '2023-10-01',
		intelligence_score: 4.5,
		speed: 3.5,
		multimodal: false,
		reasoning: true,
		included: true,
		credit_multiple: 7,
		research: false
	},
	'GPT-4.1 nano': {
		organization: 'OpenAI',
		hosted_in: 'EU',
		description: 'Fastest GPT 4.1 model. Cost-effective for simpler tasks like classification.',
		context_window: '200K',
		knowledge_cutoff: '2024-05-31',
		intelligence_score: 2.5,
		speed: 5.0,
		multimodal: true,
		reasoning: false,
		included: true,
		credit_multiple: 1,
		research: false
	},
	"GPT 4.1": {
		organization: 'OpenAI',
		hosted_in: 'EU',
		description: "OpenAI's flagship, highest-performance processor. Significantly improved over GPT-4 Turbo.",
		context_window: '1M',
		knowledge_cutoff: '2024-06-01',
		intelligence_score: 3.5,
		speed: 3.0,
		multimodal: true,
		reasoning: false,
		included: true,
		credit_multiple: 6,
		research: false
	},
	"GPT-4.1 mini": {
		organization: 'OpenAI',
		hosted_in: 'EU',
		description: "Efficient all-rounder with excellent value for money. Often outperforms GPT-4o.",
		context_window: '1M',
		knowledge_cutoff: '2024-05-31',
		intelligence_score: 3.5,
		speed: 4.0,
		multimodal: true,
		reasoning: false,
		included: true,
		credit_multiple: 2,
		research: false
	},
	"GPT o3": {
		organization: 'OpenAI',
		hosted_in: 'EU',
		description: "Strongest reasoning model for mathematics, science and complex problem solving.",
		context_window: '200K',
		knowledge_cutoff: '2024-05-31',
		intelligence_score: 4.0,
		speed: 2.0,
		multimodal: true,
		reasoning: true,
		included: true,
		credit_multiple: 12,
		research: false
	},
	"GPT o4-mini": {
		organization: 'OpenAI',
		hosted_in: 'EU',
		description: "Fast, inexpensive reasoning model with strengths in coding and visual tasks.",
		context_window: '200K',
		knowledge_cutoff: '2024-05-31',
		intelligence_score: 4.0,
		speed: 3.5,
		multimodal: true,
		reasoning: true,
		included: true,
		credit_multiple: 7,
		research: false
	},
	"GPT-5": {
		organization: 'OpenAI',
		hosted_in: 'EU',
		description: "OpenAI's flagship model for coding, reasoning, and agent tasks. Highest reasoning capabilities with moderate speed for complex domains.",
		context_window: '400K',
		knowledge_cutoff: '2024-09-31',
		intelligence_score: 4.5,
		speed: 3.0,
		multimodal: true,
		reasoning: true,
	},
	"Llama 4 Maverick": {
		organization: 'Meta',
		hosted_in: 'US',
		description: 'Multimodal model for text and images. Versatile for conversation, image analysis, and code generation.',
		context_window: '1M',
		knowledge_cutoff: '2024-08-01',
		intelligence_score: 3.5,
		speed: 2.5,
		multimodal: true,
		reasoning: false,
		included: true,
		credit_multiple: 1,
		research: false
	},
	'Perplexity Sonar Deep Research': {
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
		research: true
	},
	'Perplexity Sonar Reasoning Pro': {
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
		research: true
	},
	'Perplexity Sonar Pro': {
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
		research: true
	},
	"Perplexity Sonar": {
		organization: 'Perplexity',
		hosted_in: 'US',
		description: 'Great for basic tasks.',
		context_window: '128K',
		knowledge_cutoff: null,
		intelligence_score: null,
		speed: 1.0,
		multimodal: false,
		reasoning: false,
		included: true,
		credit_multiple: 2,
		research: true
	},
	"Grok 4": {
		organization: 'xAI',
		hosted_in: 'US',
		description: "xAI's most advanced model with superior reasoning skills and distinctive communication style.",
		context_window: '256K',
		knowledge_cutoff: '2024-12-31',
		intelligence_score: 4.5,
		speed: 3.0,
		multimodal: true,
		reasoning: false,
		included: true,
		credit_multiple: 22,
		research: false
	}
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
