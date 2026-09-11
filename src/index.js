import { Container, getContainer } from "@cloudflare/containers";
import { env } from "cloudflare:workers";

export class Backend extends Container {
	defaultPort = 8000; // matches serve.py (uvicorn on $PORT, default 8000)
	sleepAfter = "10m";
	envVars = {
		ENVIRONMENT: env.ENVIRONMENT,
		ADMIN_EMAIL: env.ADMIN_EMAIL,
		EMPLOYEE_EMAIL: env.EMPLOYEE_EMAIL,
		CONTACT_PHONE: env.CONTACT_PHONE,
		CONTACT_EMAIL: env.CONTACT_EMAIL,
		COMPANY_NAME: env.COMPANY_NAME,
		COMPANY_ADDRESS: env.COMPANY_ADDRESS,
		CURRENCY: env.CURRENCY,
		WAVE_MERCHANT_NUMBER: env.WAVE_MERCHANT_NUMBER,
		ORANGE_MONEY_NUMBER: env.ORANGE_MONEY_NUMBER,
		R2_ACCOUNT_ID: env.R2_ACCOUNT_ID,
		R2_BUCKET: env.R2_BUCKET,
		// Secrets (set via `wrangler secret put NAME` or the dashboard), forwarded as-is:
		DATABASE_URL: env.DATABASE_URL,
		SECRET_KEY: env.SECRET_KEY,
		ADMIN_PASSWORD: env.ADMIN_PASSWORD,
		EMPLOYEE_PASSWORD: env.EMPLOYEE_PASSWORD,
		R2_ACCESS_KEY_ID: env.R2_ACCESS_KEY_ID,
		R2_SECRET_ACCESS_KEY: env.R2_SECRET_ACCESS_KEY,
	};
};

export default {
	async fetch(request, env) {
		const container = getContainer(env.BACKEND);
		return container.fetch(request);
	},
};
