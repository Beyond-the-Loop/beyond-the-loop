import type {
	TopModelsResponse,
	TopAssistantsResponse,
	TotalUsersResponse,
	TotalMessagesResponse,
	EngagementScoreResponse,
	PowerUsersResponse,
	TopUsersResponse,
	TotalAssistantsResponse,
	MonthlyMessageItem,
	MonthlyPercentageChangeItem,
	YearlyMessageItem,
	YearlyPercentageChangeItem
} from '$lib/apis/analytics/types';

export const EMPTY_TOP_MODELS: TopModelsResponse = { top_models: [] };
export const EMPTY_TOP_USERS: TopUsersResponse = { top_users: [] };
export const EMPTY_TOP_ASSISTANTS: TopAssistantsResponse = { top_assistants: [] };
export const EMPTY_TOTAL_USERS: TotalUsersResponse = { total_users: 0 };
export const EMPTY_TOTAL_ASSISTANTS: TotalAssistantsResponse = { total_assistants: 0 };
export const EMPTY_ENGAGEMENT_SCORE: EngagementScoreResponse = { engagement_score: 0 };

export const EMPTY_POWER_USERS: PowerUsersResponse = {
	power_users: [],
	power_users_count: 0,
	total_users: 0,
	power_users_percentage: 0
};

const EMPTY_MONTH: MonthlyMessageItem = { period: '', message_count: 0 };
const EMPTY_CHG_M: MonthlyPercentageChangeItem = { period: '', percentage_change: 0 };
const EMPTY_YEAR: YearlyMessageItem = { period: '', message_count: 0 };
const EMPTY_CHG_Y: YearlyPercentageChangeItem = { period: '', percentage_change: 0 };

export const EMPTY_TOTAL_MESSAGES: TotalMessagesResponse = {
	monthly_messages: [EMPTY_MONTH],
	monthly_percentage_changes: [EMPTY_CHG_M],
	yearly_messages: [EMPTY_YEAR],
	yearly_percentage_changes: [EMPTY_CHG_Y]
};
