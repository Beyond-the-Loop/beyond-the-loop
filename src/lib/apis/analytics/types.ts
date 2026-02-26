// src/lib/apis/analytics/types.ts

// --- Shared helpers ---
export type ISODate = string; // "YYYY-MM-DD"
export type PeriodMonth = string; // "YYYY-MM"
export type PeriodYear = string; // "YYYY"

// --- /analytics/top-models ---
export interface TopModelItem {
	model: string;
	credits_used: number;
	message_count: number;
}

export interface TopModelsResponse {
	top_models: TopModelItem[];
}

// --- /analytics/top-users ---
export interface TopUserItem {
	user_id: string;

	first_name: string;
	last_name: string;
	email: string;
	profile_image_url: string;

	credits_used: number;
	message_count: number;
	assistant_message_percentage: number;
	engagement_score: number;

	top_model: string | null;
	top_assistant: string | null;
}

export interface TopUsersResponse {
	top_users: TopUserItem[];
}

// --- /analytics/top-assistants ---
export interface TopAssistantItem {
	assistant: string;
	credits_used: number;
	message_count: number;
	profile_image_url: string;
}

export interface TopAssistantsResponse {
	top_assistants: TopAssistantItem[];
}

// --- /analytics/stats/total-messages ---
export interface MonthlyMessageItem {
	period: PeriodMonth; // "YYYY-MM"
	message_count: number;
}

export interface MonthlyPercentageChangeItem {
	period: PeriodMonth; // "YYYY-MM"
	percentage_change: number;
}

export interface YearlyMessageItem {
	period: PeriodYear; // "YYYY"
	message_count: number;
}

export interface YearlyPercentageChangeItem {
	period: PeriodYear; // "YYYY"
	percentage_change: number;
}

export interface TotalMessagesResponse {
	monthly_messages: MonthlyMessageItem[];
	monthly_percentage_changes: MonthlyPercentageChangeItem[];
	yearly_messages: YearlyMessageItem[];
	yearly_percentage_changes: YearlyPercentageChangeItem[];
}

// --- /analytics/stats/total-users ---
export interface TotalUsersResponse {
	total_users: number;
}

// --- /analytics/stats/total-assistants ---
export interface TotalAssistantsResponse {
	total_assistants: number;
}

// --- /analytics/stats/engagement-score ---
export interface EngagementScoreResponse {
	engagement_score: number; // im Backend weiterhin "adoption_rate"
}

// --- /analytics/stats/power-users (aus AnalyticsService.get_power_users_by_company) ---
export interface PowerUserItem {
	user_id: string;
	first_name: string;
	last_name: string;
	email: string;
	profile_image_url: string | null;

	credits_used: number; // Backend: float
	message_count: number;
}

export interface PowerUsersResponse {
	power_users: PowerUserItem[];
	power_users_count: number;
	total_users: number;
	power_users_percentage: number;
}
