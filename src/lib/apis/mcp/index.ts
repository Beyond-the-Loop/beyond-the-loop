import { WEBUI_API_BASE_URL } from '$lib/constants';

const API_ROOT = `${WEBUI_API_BASE_URL}/mcp-servers`;

export type MCPAuthType = 'bearer' | 'oauth' | null;

export type MCPServerForm = {
	name: string;
	description?: string | null;
	url: string;
	transport: 'sse' | 'streamable_http';
	auth_type?: MCPAuthType;
	// Plaintext bearer token. Only sent on create or when rotating on update;
	// the backend never returns a stored token to the client.
	auth_token?: string | null;
	enabled?: boolean;
	tool_filter?: string[] | null;
	// OAuth config (optional; issuer URL defaults to `url`, client creds via DCR)
	oauth_issuer_url?: string | null;
	oauth_scope?: string | null;
	oauth_client_id?: string | null;
	oauth_client_secret?: string | null;
};

export type MCPServerResponse = {
	id: string;
	name: string;
	description: string | null;
	url: string;
	transport: 'sse' | 'streamable_http';
	auth_type: string | null;
	has_auth_token: boolean;
	enabled: boolean;
	tool_filter: string[] | null;
	template_slug: string | null;
	oauth_issuer_url: string | null;
	oauth_scope: string | null;
	oauth_granted_scope: string | null;
	oauth_principal_label: string | null;
	oauth_access_token_expires_at: number | null;
	oauth_last_error: string | null;
	has_oauth_client_secret: boolean;
	has_oauth_access_token: boolean;
	has_oauth_refresh_token: boolean;
	created_at: number;
	updated_at: number;
};

export type MCPOAuthStartResponse = {
	authorize_url: string;
	state: string;
};

export type MCPConnectorTemplate = {
	slug: string;
	name: string;
	description: string;
	icon_url: string;
	server_url: string;
	transport: 'sse' | 'streamable_http';
	issuer_url: string;
	scope: string | null;
	requires_user_credentials: boolean;
	requires_tenant_id: boolean;
	credentials_help_url: string | null;
	oauth_redirect_uri: string;
};

export type InstallTemplateBody = {
	client_id?: string;
	client_secret?: string;
	tenant_id?: string;
};

export type TestConnectionResult = {
	success: boolean;
	transport: string;
	tools?: string[] | null;
	message?: string | null;
};

const request = async <T>(token: string, path: string, init: RequestInit = {}): Promise<T> => {
	const res = await fetch(`${API_ROOT}${path}`, {
		...init,
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`,
			...(init.headers || {})
		}
	});
	if (!res.ok) {
		const err = await res.json().catch(() => ({ detail: res.statusText }));
		throw err?.detail ?? 'Request failed';
	}
	return res.json();
};

export const getMCPServers = (token: string) =>
	request<MCPServerResponse[]>(token, '/');

export const getMCPServer = (token: string, id: string) =>
	request<MCPServerResponse>(token, `/${encodeURIComponent(id)}`);

export const createMCPServer = (token: string, form: MCPServerForm) =>
	request<MCPServerResponse>(token, '/create', {
		method: 'POST',
		body: JSON.stringify(form)
	});

export const updateMCPServer = (token: string, id: string, form: MCPServerForm) =>
	request<MCPServerResponse>(token, `/${encodeURIComponent(id)}/update`, {
		method: 'POST',
		body: JSON.stringify(form)
	});

export const deleteMCPServer = (token: string, id: string) =>
	request<boolean>(token, `/${encodeURIComponent(id)}/delete`, { method: 'DELETE' });

export const testMCPServerConnection = (token: string, form: MCPServerForm) =>
	request<TestConnectionResult>(token, '/test-connection', {
		method: 'POST',
		body: JSON.stringify(form)
	});

export const testExistingMCPServerConnection = (token: string, id: string) =>
	request<TestConnectionResult>(token, `/${encodeURIComponent(id)}/test-connection`, {
		method: 'POST'
	});

export const startMCPOAuth = (token: string, id: string) =>
	request<MCPOAuthStartResponse>(token, `/${encodeURIComponent(id)}/oauth/start`, {
		method: 'POST'
	});

export const disconnectMCPOAuth = (token: string, id: string) =>
	request<boolean>(token, `/${encodeURIComponent(id)}/oauth/disconnect`, {
		method: 'POST'
	});

export const getConnectorCatalog = (token: string) =>
	request<MCPConnectorTemplate[]>(token, '/catalog');

export const installConnectorTemplate = (
	token: string,
	slug: string,
	body: InstallTemplateBody = {}
) =>
	request<MCPServerResponse>(token, `/catalog/${encodeURIComponent(slug)}/install`, {
		method: 'POST',
		body: JSON.stringify(body)
	});
