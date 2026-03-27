export interface SignupForm {
	email: string;
	signup_token: string;
	first_name: string;
	last_name: string;
	position: string;
	phone: string;
	profile_image_url: string;
	workspace_name: string;
	workspace_logo: string;
	subdomain: string;
	billing_country: string;
	invites: InviteEntry[];
}

export interface InviteEntry {
	email: string;
	role: 'user' | 'admin';
}
